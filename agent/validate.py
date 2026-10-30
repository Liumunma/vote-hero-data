"""發布前的最後一道關卡。任何一項不合格就以非零代碼結束，publish.sh 便不會 push。

用法：python3 agent/validate.py
"""
import os
import sys
from datetime import datetime

from common import OUT, PARTIES, CATEGORIES, POLL_LIKE, load, is_sealed, now_tw, sha1_of

errors = []


def err(msg):
    errors.append(msg)


def main():
    now = now_tw()
    sealed_now = is_sealed(now)
    docs = {}
    for name in ("meta", "candidates", "sentiment", "forecast", "events", "results"):
        path = os.path.join(OUT, name + ".json")
        try:
            docs[name] = load(path)
        except Exception as exc:  # noqa: BLE001 — 任何讀取錯誤都要擋下
            err("%s.json 無法讀取：%s" % (name, exc))
        if docs.get(name) is None:
            err("%s.json 不存在" % name)
        elif os.path.getsize(path) > 2_000_000:
            err("%s.json 超過 2MB" % name)
    if errors:
        return

    meta, cands = docs["meta"], docs["candidates"]
    for key in ("schema", "updatedAt", "mode", "pollInterval", "blackoutStart", "pollsClose", "files"):
        if key not in meta:
            err("meta 缺少 %s" % key)
    if not 10 <= meta.get("pollInterval", 0) <= 7200:
        err("pollInterval 超出範圍")
    for name, digest in meta.get("files", {}).items():
        if sha1_of(os.path.join(OUT, name + ".json")) != digest:
            err("meta.files.%s 雜湊值與檔案不符" % name)

    ids = {}
    race_ids = set()
    tiles = set()
    for race in cands["races"]:
        race_ids.add(race["id"])
        t = race["tile"]
        for dx in range(t.get("w", 1)):
            for dy in range(t.get("h", 1)):
                cell = (t["x"] + dx, t["y"] + dy)
                if cell in tiles:
                    err("地圖格子重疊：%s %s" % (race["id"], cell))
                tiles.add(cell)
        numbers = [c["number"] for c in race["candidates"] if c.get("number") is not None]
        if len(numbers) != len(set(numbers)):
            err("%s 號次重複" % race["id"])
        for c in race["candidates"]:
            if c["id"] in ids:
                err("候選人 id 重複：%s" % c["id"])
            ids[c["id"]] = race["id"]
            if c["party"] not in PARTIES:
                err("%s 政黨代碼錯誤" % c["id"])
    if len(race_ids) != 22:
        err("選區數量應為 22，目前 %d" % len(race_ids))

    # 選罷法 §53：任何時候都不得發布具民意調查外觀的數字
    if docs["sentiment"].get("races"):
        err("sentiment 必須是空的（不發布好感度、拔河、聲量）")
    if docs["forecast"].get("races"):
        err("forecast 必須是空的（不發布勝率、預估得票）")

    today = now.strftime("%Y-%m-%d")
    for ev in docs["events"]["events"]:
        if ev["raceId"] not in race_ids:
            err("事件 %s 選區錯誤" % ev["id"])
        if ev["category"] not in CATEGORIES:
            err("事件 %s 分類錯誤" % ev["id"])
        if ev["date"] > today:
            err("事件 %s 日期在未來" % ev["id"])
        if not ev["sources"] or not all(s["url"].startswith("https://") for s in ev["sources"]):
            err("事件 %s 來源錯誤" % ev["id"])
        for imp in ev["impacts"]:
            if ids.get(imp["candidateId"]) != ev["raceId"]:
                err("事件 %s 影響對象不在選區" % ev["id"])
            if imp.get("delta") is not None:
                err("事件 %s 不得有加減分" % ev["id"])
        if ev["category"] == "poll" or POLL_LIKE.search(ev["title"] + ev["summary"]):
            err("事件 %s 含民調或支持度數字" % ev["id"])

    for rid, r in docs["results"].get("races", {}).items():
        for cid in r.get("votes", {}):
            if ids.get(cid) != rid:
                err("開票 %s 候選人錯誤 %s" % (rid, cid))

    try:
        datetime.fromisoformat(meta["updatedAt"])
    except ValueError:
        err("meta.updatedAt 格式錯誤")


if __name__ == "__main__":
    main()
    if errors:
        print("驗證失敗（%d 項）：" % len(errors))
        for e in errors:
            print(" - " + e)
        sys.exit(1)
    print("驗證通過")
