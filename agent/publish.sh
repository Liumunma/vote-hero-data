#!/bin/bash
# 驗證通過才 commit 並 push；任何一步失敗就停止，App 會繼續顯示上一版資料。
set -euo pipefail
cd "$(dirname "$0")/.."

python3 agent/validate.py

git add -A docs agent/state
if git diff --cached --quiet; then
  echo "沒有變更，不需發布"
  exit 0
fi
# 公開 repo 一律用專案署名，不露出個人或雲端環境的名字
git -c user.name="投票勇者" -c user.email="noreply@votehero.urpig.com" \
  commit -q -m "資料更新 $(TZ=Asia/Taipei date '+%Y-%m-%d %H:%M')"
for i in 1 2 3; do
  if git push -q; then
    echo "已發布"
    exit 0
  fi
  git -c user.name="投票勇者" -c user.email="noreply@votehero.urpig.com" pull --rebase -q
done
echo "push 失敗" >&2
exit 1
