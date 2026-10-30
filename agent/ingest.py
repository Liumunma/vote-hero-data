"""把 Agent 這一輪寫進 agent/inbox/ 的蒐集結果併入 agent/state/。

用法：python3 agent/ingest.py            # 處理 inbox 內所有 .json
自動擋掉：不在白名單的來源、格式錯誤、二次檢查沒過的事件、重複事件。
原文比對（factcheck.py）：候選人姓名、數字、引述都要出現在來源網頁，否則擋掉。
依選罷法 §53 另外擋掉：民調類事件、標題或摘要含民調／支持度數字的事件；投票日 16:00 前不收任何新事件。
民調與聲量一律不收、不存（投票勇者不發布具民意調查外觀的資料）。
被擋掉的項目記在 agent/state/rejected.jsonl，方便日後檢討；處理完的 inbox 檔直接刪除，不公開。
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

import factcheck
from common import INBOX, STATE, OUT, CATEGORIES, POLLS_CLOSE, unsafe_reason, load, save, now_tw, iso, days_between

MAX_TITLE = 22
MAX_SUMMARY = 120



def election_day_quiet(now):
    """投票日 00:00 到 16:00 投票截止前，不發新戰報。"""
    return now.strftime("%Y-%m-%d") == POLLS_CLOSE.strftime("%Y-%m-%d") and now < POLLS_CLOSE


def domain_allowed(url, allowed):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in allowed)


def bigrams(text):
    t = re.sub(r"\s+", "", text)
    return {t[i:i + 2] for i in range(len(t) - 1)}


def similar(a, b):
    x, y = bigrams(a), bigrams(b)
    if not x or not y:
        return False
    return len(x & y) / len(x | y) >= 0.5


def reject(log, kind, item, reason):
    log.append({"at": iso(now_tw()), "kind": kind, "reason": reason, "item": item})


def check_event(ev, races, allowed, today):
    race = races.get(ev.get("raceId"))
    if race is None:
        return "未知的 raceId"
    if not (ev.get("review") or {}).get("ok"):
        return "二次檢查未通過"
    title, summary = ev.get("title", ""), ev.get("summary", "")
    if not title or len(title) > MAX_TITLE:
        return "標題空白或超過 %d 字" % MAX_TITLE
    if not summary or len(summary) > MAX_SUMMARY:
        return "摘要空白或超過 %d 字" % MAX_SUMMARY
    if ev.get("category") not in CATEGORIES:
        return "未知的分類"
    unsafe = unsafe_reason(ev)
    if unsafe:
        return unsafe
    impact = ev.get("impact")
    if not isinstance(impact, int) or not 1 <= impact <= 5:
        return "impact 必須是 1~5 的整數"
    date = ev.get("date", "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date) or days_between(today, date) > 0:
        return "日期錯誤或在未來"
    if days_between(date, today) > 3:
        return "事件太舊（超過 3 天）"
    ids = {c["id"] for c in race["candidates"]}
    effects = ev.get("effects") or []
    if not effects:
        return "沒有影響對象"
    for e in effects:
        if e.get("candidateId") not in ids:
            return "影響對象不在這個選區"
    sources = [s for s in ev.get("sources") or [] if s.get("url", "").startswith("https://")]
    if not sources:
        return "沒有 https 來源"
    for s in sources:
        if not domain_allowed(s["url"], allowed):
            return "來源不在白名單：%s" % s["url"]
    return None


def merge_event(events, ev):
    """與既有事件重複時合併來源並回傳 True。"""
    urls = {s["url"] for s in ev["sources"]}
    for old in events:
        same_url = urls & {s["url"] for s in old["sources"]}
        near = (old["raceId"] == ev["raceId"] and abs(days_between(old["date"], ev["date"])) <= 1
                and similar(old["title"], ev["title"]))
        if same_url or near:
            known = {s["url"] for s in old["sources"]}
            for s in ev["sources"]:
                if s["url"] not in known:
                    old["sources"].append({"name": s.get("name", ""), "url": s["url"]})
            return True
    return False


def main():
    cands = load(os.path.join(OUT, "candidates.json"))
    races = {r["id"]: r for r in cands["races"]}
    cfg = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "sources.json"))
    allowed = list(cfg["allowed"].keys())
    today = now_tw().strftime("%Y-%m-%d")

    events = load(os.path.join(STATE, "events.json"), [])
    rejected = []
    quiet = election_day_quiet(now_tw())
    added = merged = 0

    files = sorted(f for f in os.listdir(INBOX) if f.endswith(".json")) if os.path.isdir(INBOX) else []
    for name in files:
        path = os.path.join(INBOX, name)
        try:
            batch = load(path)
        except json.JSONDecodeError as exc:
            print("無法讀取 %s：%s" % (name, exc), file=sys.stderr)
            os.replace(path, path + ".bad")
            continue

        for ev in batch.get("events", []):
            reason = "投票日 16:00 前不發新戰報" if quiet else check_event(ev, races, allowed, today)
            if not reason and not os.environ.get("VOTEHERO_SKIP_FACTCHECK"):
                reason = factcheck.check(ev, races[ev["raceId"]])
            if reason:
                reject(rejected, "event", ev, reason)
                continue
            clean = {
                "date": ev["date"], "raceId": ev["raceId"], "title": ev["title"].strip(),
                "summary": ev["summary"].strip(), "category": ev["category"], "impact": ev["impact"],
                "effects": [{"candidateId": e["candidateId"]} for e in ev["effects"]],
                "sources": [{"name": s.get("name", ""), "url": s["url"]} for s in ev["sources"]],
            }
            if merge_event(events, clean):
                merged += 1
                continue
            n = sum(1 for e in events if e["date"] == clean["date"] and e["raceId"] == clean["raceId"]) + 1
            clean["id"] = "%s-%s-%d" % (clean["date"], clean["raceId"], n)
            events.append(clean)
            added += 1

        # 民調與聲量不收；處理完的原始檔刪除，不留在公開 repo
        os.remove(path)

    events.sort(key=lambda e: (e["date"], e["id"]))
    save(os.path.join(STATE, "events.json"), events)
    if rejected:
        with open(os.path.join(STATE, "rejected.jsonl"), "a", encoding="utf-8") as f:
            for r in rejected:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("inbox %d 檔：新增 %d、合併 %d、擋掉 %d" % (len(files), added, merged, len(rejected)))


if __name__ == "__main__":
    main()
