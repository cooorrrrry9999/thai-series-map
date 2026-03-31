#!/bin/bash

# ============================================================
# Thai Series Map — デプロイスクリプト
# 使い方: ./deploy.sh
# ============================================================

set -e

GITHUB_USER="cooorrrrry9999"
REPO="thai-series-map"

# ── 作業フォルダに移動 ──────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
echo "📁 フォルダ: $SCRIPT_DIR"

# ── Gitが入っているか確認 ───────────────────────────────────
if ! command -v git &> /dev/null; then
  echo "❌ Gitがインストールされていません"
  echo "   https://git-scm.com からインストールしてください"
  exit 1
fi

# ── 初回のみ: Gitリポジトリ初期化 ──────────────────────────
if [ ! -d ".git" ]; then
  echo "🔧 Gitリポジトリを初期化します..."
  git init
  git remote add origin "https://github.com/${GITHUB_USER}/${REPO}.git"
  echo "✅ 初期化完了"
fi

# ── index.html が存在するか確認 ────────────────────────────
if [ ! -f "index.html" ]; then
  echo "❌ index.html が見つかりません"
  echo "   このスクリプトと同じフォルダに index.html を置いてください"
  exit 1
fi

# ── ステージング & コミット ────────────────────────────────
echo ""
echo "📦 変更ファイルをまとめています..."
git add .

if git diff --cached --quiet; then
  echo "ℹ️  変更がないためスキップします（すでに最新です）"
else
  TIMESTAMP=$(date "+%Y-%m-%d %H:%M")
  git commit -m "🌸 update: ${TIMESTAMP}"
  echo "✅ コミット完了"
fi

# ── GitHub へプッシュ ──────────────────────────────────────
echo "🚀 GitHubにアップロードしています..."
git branch -M main
git push -u origin main

# ── 完了メッセージ ─────────────────────────────────────────
echo ""
echo "✅ デプロイ完了！"
echo ""
echo "🌐 公開URL（数分後にアクセスできます）:"
echo "   https://${GITHUB_USER}.github.io/${REPO}/"
echo ""
echo "📱 スマホでこのURLを開いて「ホーム画面に追加」でアプリ化できます"
