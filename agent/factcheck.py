"""戰報原文比對：實際下載來源網頁，確認事件卡寫的東西真的出現在原文裡。

用法（ingest.py 會自動呼叫）：
    reason = check(event, race)   # None = 通過；字串 = 擋掉的原因
單獨測試某則：python3 agent/factcheck.py <網址> <要找的字>...

檢查項目：
1. 至少一個來源網頁打得開。
2. 相關候選人的姓名都出現在原文。
3. 標題與摘要裡的每個數字（日期、金額、人數…）都出現在原文。
4. 事件日期的年月日例外（原文常寫「昨」「今」）。
5. 摘要裡「」內的引述，原文要有相同的字（允許標點與空白差異）。
打不開的來源不算錯，但全部打不開就不收。
"""
import html
import re
import subprocess
import sys
import time
import unicodedata
from urllib.request import Request, urlopen

TIMEOUT = 15
MAX_BYTES = 3_000_000
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"

_cache = {}


def normalize(text):
    """全形轉半形、去掉空白與常見標點，方便比對。"""
    t = unicodedata.normalize("NFKC", text)
    t = t.replace("臺", "台")
    return re.sub(r"[\s　，。、；：！？「」『』（）()《》〈〉“”‘’\"'·・\-—…]", "", t)


_errors = {}


def page_text(url):
    if url in _cache:
        return _cache[url]
    text = None
    try:
        try:
            body = download(url)
        except Exception:
            time.sleep(4)   # 有些媒體偶爾擋雲端連線，隔幾秒再試一次
            body = download(url)
        body = re.sub(r"(?is)<(script|style|noscript|nav|aside|footer)[^>]*>.*?</\1>", " ", body)
        # 只取正文段落、標題與描述，避免側欄「相關新聞」裡的其他人名混進來
        metas = re.findall(r'(?i)<meta[^>]+(?:name|property)="(?:description|og:description|og:title)"[^>]+content="([^"]*)"', body)
        heads = re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", body)
        paras = [re.sub(r"(?s)<[^>]+>", " ", p) for p in re.findall(r"(?is)<p[^>]*>(.*?)</p>", body)]
        # 正文段落是 40~800 字的完整句子；側欄的相關新聞是很短的標題，或整串塞在一個超長段落裡，都排除
        paras = [p for p in paras if 40 <= len(normalize(p)) <= 800]
        parts = metas + heads + paras
        text = html.unescape(re.sub(r"(?s)<[^>]+>", " ", " ".join(parts)))
        if len(normalize(text)) < 80:
            text = None   # 抓不到正文就當作打不開
    except Exception as exc:
        print("factcheck：無法下載 %s（%s）" % (url, exc), file=sys.stderr)
        _errors[url] = str(exc)[:160]
        text = None
    _cache[url] = text
    return text


def download(url):
    """先用 Python 下載；失敗（例如雲端環境要走代理或自訂憑證）再改用 curl。"""
    try:
        with urlopen(Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"}),
                     timeout=TIMEOUT) as resp:
            raw = resp.read(MAX_BYTES)
            charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="ignore")
    except Exception as exc:
        first = exc
    try:
        out = subprocess.run(["curl", "-sSL", "--max-time", str(TIMEOUT), "-A", UA,
                              "-H", "Accept-Language: zh-TW,zh;q=0.9", url],
                             capture_output=True, timeout=TIMEOUT + 5)
        if out.returncode == 0 and out.stdout:
            return out.stdout[:MAX_BYTES].decode("utf-8", errors="ignore")
        raise RuntimeError("python: %s；curl: %s" % (first, out.stderr.decode(errors="ignore").strip()[:200]))
    except FileNotFoundError:
        raise RuntimeError("python: %s；curl 不存在" % first)


def numbers_in(text):
    """抓出數字（含小數），忽略單獨的 0~9 以外的雜訊不處理，全部都要比對。"""
    t = unicodedata.normalize("NFKC", text)
    return set(re.findall(r"\d+(?:\.\d+)?", t))


def quotes_in(text):
    return [q for q in re.findall(r"「([^」]{4,})」", text)]


def check(ev, race):
    urls = [s["url"] for s in ev.get("sources", [])]
    texts = [t for t in (page_text(u) for u in urls) if t]
    if not texts:
        detail = "；".join(_errors.get(u, "抓不到正文") for u in urls)
        return "原文比對：來源網頁都打不開（%s）" % detail
    raw = " ".join(texts)
    norm = normalize(raw)
    raw_numbers = set(re.findall(r"\d+(?:\.\d+)?", unicodedata.normalize("NFKC", raw)))

    names = {c["id"]: c["name"] for c in race["candidates"]}
    for e in ev.get("effects", []):
        name = names.get(e.get("candidateId"))
        if name and normalize(name) not in norm:
            return "原文比對：原文沒有提到 %s" % name

    # 事件日期的年月日可以出現（原文常寫「昨」「今」，換算成日期不算捏造）
    y, m, d = (ev.get("date") or "0-0-0").split("-")
    date_parts = {y, str(int(m)), str(int(d)), m, d}
    for n in numbers_in(ev.get("title", "") + ev.get("summary", "")):
        if n not in raw_numbers and n not in date_parts:
            return "原文比對：原文找不到數字 %s" % n

    for q in quotes_in(ev.get("summary", "")):
        if normalize(q) not in norm:
            return "原文比對：原文找不到引述「%s」" % q
    return None


if __name__ == "__main__":
    url, *needles = sys.argv[1:]
    t = page_text(url)
    if not t:
        print("打不開")
        sys.exit(1)
    n = normalize(t)
    for w in needles:
        print(w, "✓" if normalize(w) in n else "✗")
