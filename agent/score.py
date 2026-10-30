"""把 agent/state/ 的事件整理成 docs/v1/ 的 App 資料。

用法：python3 agent/score.py

依《公職人員選舉罷免法》第 53 條，選舉公告後不得發布未載明法定事項、「具民意調查外觀」的選舉資料。
所以投票勇者不計算、也不發布任何支持度、好感度、聲量、事件加減分、勝率或預估得票，
只發布候選人名單、新聞事件（標題、摘要、相關候選人、來源連結）與中選會開票數字。
sentiment.json／forecast.json 為了舊版 App 相容仍會產生，但內容永遠是空的。
"""
import os

from common import (OUT, STATE, BLACKOUT_START, POLLS_CLOSE, ELECTION_DAY, RESULTS_LIVE_URL, load, save, now_tw, iso,
                    mode_for, poll_interval_for, sha1_of)


def event_status(ev):
    """影響力大但只有一家媒體報導的事件標為「觀察中」。"""
    names = {s.get("name") or s["url"] for s in ev["sources"]}
    if ev["impact"] >= 4 and len(names) < 2:
        return "watching"
    return "scored"


def main():
    now = now_tw()
    stamp = iso(now)

    events = load(os.path.join(STATE, "events.json"), [])

    save(os.path.join(OUT, "sentiment.json"), {"updatedAt": stamp, "sealed": True, "races": {}})
    save(os.path.join(OUT, "forecast.json"), {"updatedAt": stamp, "sealed": True, "races": {}})

    recent = sorted(events, key=lambda e: (e["date"], e["id"]), reverse=True)[:120]
    out_events = []
    for ev in recent:
        out_events.append({
            "id": ev["id"], "date": ev["date"], "raceId": ev["raceId"], "title": ev["title"],
            "summary": ev["summary"], "category": ev["category"], "status": event_status(ev),
            # 只列出相關候選人，不附任何分數
            "impacts": [{"candidateId": e["candidateId"], "delta": None} for e in ev["effects"]],
            "sources": ev["sources"],
        })
    save(os.path.join(OUT, "events.json"), {"updatedAt": stamp, "events": out_events})

    results_path = os.path.join(OUT, "results.json")
    if not os.path.exists(results_path):
        save(results_path, {"updatedAt": stamp, "source": "中選會", "live": False, "races": {}})

    names = ["candidates", "sentiment", "forecast", "events", "results"]
    meta = {
        "schema": 1,
        "updatedAt": stamp,
        "mode": mode_for(now),
        "pollInterval": poll_interval_for(now),
        "electionDay": ELECTION_DAY,
        "blackoutStart": iso(BLACKOUT_START),
        "pollsClose": iso(POLLS_CLOSE),
        "resultsURL": RESULTS_LIVE_URL,
        "minAppVersion": "1.0.0",
        "sealed": True,
        "notice": "投票勇者不做民調與選情預測；戰報整理自公開新聞，開票以中選會公告為準。",
        "files": {n: sha1_of(os.path.join(OUT, n + ".json")) for n in names},
    }
    save(os.path.join(OUT, "meta.json"), meta)
    print("score：%s 模式=%s 事件=%d" % (stamp, meta["mode"], len(events)))


if __name__ == "__main__":
    main()
