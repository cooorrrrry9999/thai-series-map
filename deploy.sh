#!/bin/bash

# ============================================================
# Thai Series Map — デプロイスクリプト（自動取り込み版）
# 使い方: ./deploy.sh
#
#   1. admin.html で「📤 公開用 data.json を書き出す」を押す
#   2. このスクリプトを実行する（ダブルクリック or ./deploy.sh）
#      → ダウンロードフォルダの最新 data.json を自動で取り込み、
#        壊れていないか検査して、GitHubにバックアップ後、
#        Firebase Hosting（https://thai-series-map.web.app/）に公開します
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

# ── ②b 既知の重複統合・絵文字正規化（Firestore側が掃除されるまでの保険）──────
# エクスポートし直すたびに重複・旧絵文字が復活するのを防ぐ。詳細は scripts/clean_data.py 参照
if [ -f "data.json" ] && [ -f "scripts/clean_data.py" ] && command -v python3 &> /dev/null; then
  echo "🧹 data.json をクリーンアップしています..."
  python3 scripts/clean_data.py data.json
fi

# ── ②c スポット別の静的ページ（プリレンダ）と sitemap.xml を生成 ──
#   各スポットを /spot/<id>/ の静的HTML化し、検索結果に固有の title/説明を出す（SEO・CTR改善）。
#   sitemap.xml も同スクリプトが /spot/<id>/ 形式で生成する（詳細は scripts/prerender.py）。
if [ -f "data.json" ] && [ -f "scripts/prerender.py" ] && command -v python3 &> /dev/null; then
  python3 scripts/prerender.py data.json
fi

# ── ②d 静的スポット一覧を index.html に差し込み（SEO：JS実行なしでも全スポットの名称・作品・住所をクロールさせる）──
if [ -f "data.json" ] && [ -f "index.html" ] && command -v python3 &> /dev/null; then
  python3 - <<'PYEOF'
import json, html, re
d = json.load(open('data.json'))
# location_id → その地に登場する作品名・シーン説明
apps_by_loc = {}
for a in d.get('appearances', []):
    lid = a.get('location_id')
    if not lid:
        continue
    apps_by_loc.setdefault(lid, []).append(a)

def esc(s):
    return html.escape(str(s or '').strip())

items = []
for l in sorted(d.get('locations', []), key=lambda x: (x.get('name') or '')):
    lid = l.get('id')
    if not lid:
        continue
    name = esc(l.get('name'))
    cat = esc(l.get('category'))
    addr = esc(l.get('address'))
    apps = apps_by_loc.get(lid, [])
    series = []
    for a in apps:
        s = (a.get('series') or '').strip()
        if s and s not in series:
            series.append(s)
    scenes = []
    for a in apps:
        sc = (a.get('scene_desc') or '').strip()
        if sc and sc not in scenes:
            scenes.append(sc)
    meta = []
    if cat:
        meta.append(cat)
    if series:
        meta.append('作品: ' + esc('・'.join(series)) + ' ロケ地')
    if addr:
        meta.append(addr)
    if scenes:
        meta.append(esc(' / '.join(scenes[:3])))
    meta_html = '｜'.join(meta)
    items.append(
        f'<li><a href="spot/{esc(lid)}/">{name}</a>'
        + (f' <span class="dir-meta">{meta_html}</span>' if meta_html else '')
        + '</li>'
    )

block = (
    '<!--SPOT_DIRECTORY_START-->\n'
    '<section id="spot-directory" aria-label="タイドラマ・タイGL 聖地巡礼スポット一覧">\n'
    '<h2>タイドラマ・タイGL 聖地巡礼スポット一覧 / All Thai GL Filming Locations</h2>\n'
    '<ul>\n' + '\n'.join(items) + '\n</ul>\n'
    '</section>\n'
    '<!--SPOT_DIRECTORY_END-->'
)

src = open('index.html', encoding='utf-8').read()
new = re.sub(
    r'<!--SPOT_DIRECTORY_START-->.*?<!--SPOT_DIRECTORY_END-->',
    lambda m: block,
    src,
    count=1,
    flags=re.S,
)
if new != src:
    open('index.html', 'w', encoding='utf-8').write(new)
    print(f"📇 静的スポット一覧を index.html に差し込みました（{len(items)} 件）")
else:
    print("⚠️  SPOT_DIRECTORY マーカーが見つからず一覧を差し込めませんでした")
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

# ── ④ GitHub へプッシュ（バックアップ用） ──────────────────
echo "🚀 GitHubにバックアップしています..."
git branch -M main
git push -u origin main

# ── ⑤ Firebase Hosting へ公開 ──────────────────────────────
if ! command -v firebase &> /dev/null; then
  echo "❌ Firebase CLI がインストールされていません"
  echo "   npm install -g firebase-tools でインストールしてください"
  exit 1
fi
echo "🚀 Firebase Hosting に公開しています..."
firebase deploy --only hosting:map

# ── 完了メッセージ ─────────────────────────────────────────
echo ""
echo "✅ デプロイ完了！"
echo ""
echo "🌐 公開URL:"
echo "   https://thai-series-map.web.app/"
echo ""
echo "📱 スマホでこのURLを開いて「ホーム画面に追加」でアプリ化できます"
