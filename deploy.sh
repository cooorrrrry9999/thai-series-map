#!/bin/bash

# ============================================================
# Thai Series Map — デプロイスクリプト
# 使い方: ./deploy.sh
# ============================================================

set -e

REPO="thai-series-map"
GITHUB_USER="cooorrrrry9999"  # ← ここにGitHubのユーザー名を入れてください（例: "yamada-hanako"）

# ユーザー名チェック
if [ -z "$GITHUB_USER" ]; then
  echo "❌ エラー: GITHUB_USER を設定してください"
  echo "   このファイルをテキストエディタで開いて、3行目の \"\" の中にGitHubユーザー名を入れてください"
  exit 1
fi

echo "🌸 Thai Series Map デプロイ開始..."
echo ""

# --- 1. 作業フォルダに移動 ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- 2. Gitが入っているか確認 ---
if ! command -v git &> /dev/null; then
  echo "❌ Gitがインストールされていません"
  echo "   https://git-scm.com からインストールしてください"
  exit 1
fi

# --- 3. 初回 or 既存リポジトリか判定 ---
if [ ! -d ".git" ]; then
  echo "📁 Gitリポジトリを初期化します..."
  git init
  git remote add origin "https://github.com/${GITHUB_USER}/${REPO}.git"
  echo "✅ 初期化完了"
fi

# --- 4. 必要なファイルの存在確認 ---
if [ ! -f "index.html" ]; then
  echo "❌ index.html が見つかりません"
  echo "   このスクリプトと同じフォルダに index.html を置いてください"
  exit 1
fi

# --- 5. ステージング & コミット ---
echo "📦 ファイルをまとめています..."
git add .

# 変更がなければスキップ
if git diff --cached --quiet; then
  echo "ℹ️  変更がないためスキップします（すでに最新です）"
else
  TIMESTAMP=$(date "+%Y-%m-%d %H:%M")
  git commit -m "🌸 update: ${TIMESTAMP}"
  echo "✅ コミット完了"
fi

# --- 6. プッシュ ---
echo "🚀 GitHubにアップロードしています..."
git branch -M main
git push -u origin main

echo ""
echo "✅ デプロイ完了！"
echo ""
echo "🌐 公開URL（数分後にアクセスできます）:"
echo "   https://${GITHUB_USER}.github.io/${REPO}/"
echo ""
echo "📱 スマホでこのURLを開いて「ホーム画面に追加」でアプリ化できます"
