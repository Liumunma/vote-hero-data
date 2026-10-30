"""共用工具：路徑、時間、選舉日曆、JSON 讀寫。只用 Python 標準函式庫（3.9+）。"""
import hashlib
import re
import json
import os
from datetime import datetime, timedelta, timezone

TW = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "agent", "state")
INBOX = os.path.join(ROOT, "agent", "inbox")
OUT = os.path.join(ROOT, "docs", "v1")

ELECTION_DAY = "2026-11-28"
BLACKOUT_START = datetime(2026, 11, 18, 0, 0, tzinfo=TW)
POLLS_CLOSE = datetime(2026, 11, 28, 16, 0, tzinfo=TW)
NIGHT_END = datetime(2026, 11, 29, 6, 0, tzinfo=TW)
FINAL_WEEK = datetime(2026, 11, 11, 0, 0, tzinfo=TW)

# 開票夜即時資料：ElectionNight/count.py 每分鐘推到 live 分支，App 透過 GitHub API 讀（帶 ETag，304 不計流量限制）。
# 被限流時 App 會退回讀 Pages 上的 v1/results.json（約每 6 分鐘更新）。
RESULTS_LIVE_URL = "https://api.github.com/repos/Liumunma/vote-hero-data/contents/results.json?ref=live"

PARTIES = {"KMT", "DPP", "TPP", "OTHER", "IND"}
CATEGORIES = {"policy", "debate", "rally", "scandal", "gaffe", "endorsement", "poll", "campaign", "other"}


def now_tw():
    """目前台灣時間；可用環境變數 VOTEHERO_NOW 覆寫（測試封關用）。"""
    override = os.environ.get("VOTEHERO_NOW")
    if override:
        return datetime.fromisoformat(override).astimezone(TW)
    return datetime.now(TW)


def iso(dt):
    return dt.astimezone(TW).replace(microsecond=0).isoformat()


def mode_for(now):
    if now < BLACKOUT_START:
        return "normal"
    if now < POLLS_CLOSE:
        return "blackout"
    if now < NIGHT_END:
        return "election_night"
    return "final"


def is_sealed(now):
    """選罷法第 53 條：投票日前十日起至投票截止，不得發布民調相關數字。"""
    return BLACKOUT_START <= now < POLLS_CLOSE


def poll_interval_for(now):
    mode = mode_for(now)
    if mode == "election_night":
        return 20
    if mode == "final":
        return 3600
    if mode == "normal" and now >= FINAL_WEEK:
        return 300
    return 900


def load(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=False) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)
    return text


def sha1_of(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:12]


def candidate_index(candidates_doc):
    """{candidateId: (race, candidate)}"""
    idx = {}
    for race in candidates_doc["races"]:
        for c in race["candidates"]:
            idx[c["id"]] = (race, c)
    return idx


def days_between(a, b):
    """a、b 為 YYYY-MM-DD，回傳 b - a 的天數。"""
    da = datetime.strptime(a, "%Y-%m-%d")
    db = datetime.strptime(b, "%Y-%m-%d")
    return (db - da).days


# 民調、支持度、百分比之類的數字一律不准出現在戰報（選罷法 §53）
POLL_LIKE = re.compile(r"\d+(\.\d+)?\s*(%|％|個?百分點|成支持)|支持度|勝率|民調.{0,6}\d|\d.{0,6}民調|領先.{0,4}\d")
