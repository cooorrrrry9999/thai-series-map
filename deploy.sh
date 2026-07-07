#!/bin/bash

# ============================================================
# Thai Series Map — デプロイスクリプト（自動取り込み版）
# 使い方: ./deploy.sh
#
#   1. admin.html で「📤 公開用 data.json を書き出す」を押す
#   2. このスクリプトを実行する（ダブルクリック or ./deploy.sh）
#      → ダウンロードフォルダの最新 data.json を自動で取り込み、
#        壊れていないか検査して、GitHub に公開します
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

# ── ① ダウンロードフォルダの最新 data.json を自動で取り込む ──
# Mac / Linux / Windows(Git Bash) のダウンロードフォルダを探す
DL=""
for d in "$HOME/Downloads" "$HOME/ダウンロード" "$USERPROFILE/Downloads"; do
  if [ -d "$d" ]; then DL="$d"; break; fi
done

if [ -n "$DL" ]; then
  # data.json / data (1).json … のうち最も新しいものを1つ選ぶ
  LATEST="$(ls -t "$DL"/data*.json 2>/dev/null | head -n 1 || true)"
  if [ -n "$LATEST" ]; then
    echo ""
    echo "📥 ダウンロードフォルダで新しいデータを見つけました:"
    echo "   $LATEST"
    read -r -p "   これを公開用 data.json として取り込みますか？ [Y/n] " ANS
    if [ "$ANS" != "n" ] && [ "$ANS" != "N" ]; then
      cp "$LATEST" "$SCRIPT_DIR/data.json"
      echo "✅ data.json を更新しました"
    else
      echo "ⓘ 取り込みをスキップしました（今ある data.json をそのまま使います）"
    fi
  fi
fi

# ── ② data.json が壊れていないか検査（事故防止）──────────────
if [ -f "data.json" ]; then
  if command -v python3 &> /dev/null; then
    if ! python3 -c "import json,sys; json.load(open('data.json'))" 2>/dev/null; then
      echo "❌ data.json が壊れています（JSONとして読めません）。デプロイを中止しました。"
      exit 1
    fi
    CNT=$(python3 -c "import json; d=json.load(open('data.json')); print(len(d.get('locations',[])))")
    echo "🔎 data.json OK（ロケ地 ${CNT}件）"
  fi
else
  echo "⚠️  data.json が見つかりません。これだとサイトはFirestoreから読み込みます（読み取り回数が増えます）。"
  read -r -p "   このまま続けますか？ [y/N] " ANS2
  if [ "$ANS2" != "y" ] && [ "$ANS2" != "Y" ]; then
    echo "中止しました。"
    exit 1
  fi
fi

# ── ②b sitemap.xml を data.json から自動生成（SEO：全スポットの直リンクを検索エンジンに知らせる）──
if [ -f "data.json" ] && command -v python3 &> /dev/null; then
  python3 - <<'PYEOF'
import json, datetime
BASE = "https://cooorrrrry9999.github.io/thai-series-map/"
d = json.load(open('data.json'))
today = datetime.date.today().isoformat()
urls = [f'  <url><loc>{BASE}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>']
for l in d.get('locations', []):
    if l.get('id'):
        urls.append(f'  <url><loc>{BASE}?spot={l["id"]}</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq></url>')
xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + '\n'.join(urls) + '\n</urlset>\n'
open('sitemap.xml', 'w').write(xml)
print(f"🔎 sitemap.xml を生成しました（{len(urls)} URL）")
PYEOF
fi

# ── ③ ステージング & コミット ──────────────────────────────
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

# ── ④ GitHub へプッシュ ────────────────────────────────────
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
