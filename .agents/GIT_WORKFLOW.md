# Git 工作流（速查）

每个改动走功能分支 + PR，**不直接 push `main`**。

```bash
git checkout main && git pull origin main    # ① 切分支前先同步最新 main
git checkout -b feat/xxx                      # ② 从最新 main 切（前缀 feat/fix/docs/refactor）
#  ...改动 → 自测...
git commit -m "feat: ..."                     # ③ 约定式提交
git push -u origin feat/xxx
gh pr create --base main --head feat/xxx      # ④ 开 PR，review 后合并
# 合并后：
git checkout main && git pull origin main     # ⑤ 拉最新，再切下一个分支
git branch -d feat/xxx                        #    删本地（远端合并时可自动删）
```

## 纪律

- **切分支前必须先 `pull` main**：基于旧 main 切会一开局就分叉（本仓库 `main` 曾被分叉过）。
- **一分支一件事**，合完即删。
- 功能分支做得久、期间 main 有更新：合并前先把 main 合进分支解冲突，再请求合并。
- 一个 PR 只做一类改动，无关改动另起分支（如本文件就单独走 `docs/` 分支）。
