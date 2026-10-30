# 投票勇者資料格式 v1

App 讀取 `https://liumunma.github.io/vote-hero-data/v1/` 底下的檔案。所有時間都是 ISO 8601、台灣時區（`+08:00`）。

App 每次先抓 `meta.json`（很小），`files` 裡哪個檔的雜湊值變了才下載那個檔。

## meta.json
```json
{
  "schema": 1,
  "updatedAt": "2026-10-29T20:00:00+08:00",
  "mode": "normal",                 // normal | blackout | election_night | final
  "pollInterval": 900,              // 秒；App 依此輪詢 meta.json
  "electionDay": "2026-11-28",
  "blackoutStart": "2026-11-18T00:00:00+08:00",
  "pollsClose": "2026-11-28T16:00:00+08:00",
  "resultsURL": null,               // 開票夜即時資料位址（null = 用 v1/results.json）
  "minAppVersion": "1.0.0",
  "notice": "投票勇者不做民調與選情預測…",
  "files": { "candidates": "sha1…", "sentiment": "sha1…", "forecast": "sha1…", "events": "sha1…", "results": "sha1…" }
}
```

## candidates.json
```json
{
  "updatedAt": "…",
  "races": [{
    "id": "taipei", "name": "臺北市", "short": "北市", "kind": "municipality",   // municipality | county
    "tile": { "x": 4, "y": 1, "w": 1, "h": 1 },     // 像素地圖格子座標
    "hot": 3,                                        // 關注度 1~3
    "candidates": [{
      "id": "taipei-2", "number": 2, "name": "…",
      "party": "KMT",                                // KMT | DPP | TPP | OTHER | IND
      "partyName": "中國國民黨", "incumbent": true, "note": null,
      "look": { "hair": 3, "hairColor": 0, "glasses": false, "acc": 0 }   // 像素頭像參數，純外觀
    }]
  }]
}
```

## sentiment.json／forecast.json（永遠是空的）
依選罷法 §53，投票勇者不發布好感度、拔河比例、聲量、勝率、預估得票等具民意調查外觀的數字。
這兩個檔案只為了舊版 App 相容而保留：`{"updatedAt": "…", "sealed": true, "races": {}}`。`validate.py` 會擋下任何非空內容。

## events.json（最新 120 則；impacts 只列相關候選人，delta 永遠是 null）
```json
{
  "updatedAt": "…",
  "events": [{
    "id": "2026-10-29-taipei-debate",
    "date": "2026-10-29", "raceId": "taipei",
    "title": "首場電視辯論 交通政見交鋒",
    "summary": "兩三句中立摘要。",
    "category": "debate",            // policy | debate | rally | scandal | gaffe | endorsement | campaign | other（poll 已停用）
    "status": "scored",              // scored（一般）| watching（觀察中：影響力大但只有一家報導）
    "impacts": [ { "candidateId": "taipei-2", "delta": null } ],
    "sources": [ { "name": "中央社", "url": "https://…" } ]
  }]
}
```

## results.json（開票夜）
```json
{
  "updatedAt": "…", "source": "中選會", "live": true,
  "races": { "taipei": {
    "stationsReported": 812, "stationsTotal": 1560,
    "votes": { "taipei-2": 412345, "taipei-3": 398765 },
    "elected": null                   // 當選確定後填候選人 id
  } }
}
```
