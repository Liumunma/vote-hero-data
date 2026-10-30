# 投票勇者 資料庫（vote-hero-data）

「投票勇者」iOS App 的公開資料與戰報 Agent。

- `docs/`：GitHub Pages 網站。`docs/v1/*.json` 是 App 讀的資料（格式見 `SCHEMA.md`），`docs/index.html` 是說明與隱私權政策頁。
- `agent/`：戰報 Agent。`AGENT.md` 是排程 Claude 的工作說明，`RUBRIC.md` 是寫作規則，`score.py` 把事件整理成 App 資料。
- `live` 分支：開票夜即時資料（由開票程式每分鐘推送）。

投票勇者不做民調與選情預測，不發布任何支持度、勝率或好感度（選罷法 §53）。開票數字以中選會公告為準。
