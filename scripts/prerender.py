#!/usr/bin/env python3
# ============================================================
# Thai Series Map — スポット・プリレンダ生成
#
#   data.json から各スポットの静的HTML（spot/<id>/index.html）を生成する。
#   目的（SEO）:
#     - 検索結果に「そのスポット固有の title / description」を JS 実行なしで出す
#       （SPAは初期HTMLだと全 ?spot= が同じ title になり、CTRが伸びない）
#     - canonical を /spot/<id>/ に集約し、?spot= の重複扱いを防ぐ
#     - 可視コンテンツ＋内部リンク＋構造化データでロングテールと順位を取りにいく
#     - タイからの表示を拾うため、説明にタイ語の一文を添える
#
#   併せて sitemap.xml も /spot/<id>/ 形式で生成する（単一の正）。
#
#   使い方: python3 scripts/prerender.py [data.json]
#   （deploy.sh から自動で呼ばれる）
# ============================================================
import json, html, os, sys, shutil, datetime, re

BASE = "https://thai-series-map.web.app/"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "spot")

# ドラマのロケ地ではなく「タグ的なもの」= 作品名として推し出さない series 値
# （#spot-directory 側と同様、表示自体はするが title には使わない）
COMMON_TAG_HINTS = ("オススメ", "おすすめ", "来日", "プライベート", "イベント", "ファンミ")


def esc(s):
    return html.escape(str(s or "").strip())


def attr(s):
    # 属性値用（引用符も確実にエスケープ）
    return html.escape(str(s or "").strip(), quote=True)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build():
    data_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data.json")
    d = load(data_path)
    locations = d.get("locations", [])
    appearances = d.get("appearances", [])

    apps_by_loc = {}
    for a in appearances:
        lid = a.get("location_id")
        if lid:
            apps_by_loc.setdefault(lid, []).append(a)

    # series -> [location_id...]（同じ作品のロケ地を相互リンクするため）
    locs_by_series = {}
    for l in locations:
        lid = l.get("id")
        if not lid:
            continue
        for a in apps_by_loc.get(lid, []):
            s = (a.get("series") or "").strip()
            if s:
                locs_by_series.setdefault(s, [])
                if lid not in locs_by_series[s]:
                    locs_by_series[s].append(lid)

    name_by_id = {l.get("id"): (l.get("name") or "").strip() for l in locations if l.get("id")}

    # 出力ディレクトリを作り直す（削除済みスポットの残骸を消す）
    if os.path.isdir(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    count = 0
    sitemap_ids = []
    for l in locations:
        lid = l.get("id")
        if not lid:
            continue
        page = render_spot(l, apps_by_loc.get(lid, []), locs_by_series, name_by_id)
        spot_dir = os.path.join(OUT_DIR, lid)
        os.makedirs(spot_dir, exist_ok=True)
        with open(os.path.join(spot_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(page)
        sitemap_ids.append(lid)
        count += 1

    write_sitemap(sitemap_ids)
    print(f"🧩 プリレンダ生成: spot/<id>/index.html を {count} ページ")


def series_of(apps):
    """このロケ地の作品名（重複除去・順序維持）"""
    out = []
    for a in apps:
        s = (a.get("series") or "").strip()
        if s and s not in out:
            out.append(s)
    return out


def is_real_series(s):
    return s and not any(h in s for h in COMMON_TAG_HINTS)


def render_spot(loc, apps, locs_by_series, name_by_id):
    lid = loc["id"]
    name = (loc.get("name") or "").strip()
    category = (loc.get("category") or "").strip()
    address = (loc.get("address") or "").strip()
    memo = (loc.get("memo") or "").strip()
    lat = loc.get("lat")
    lng = loc.get("lng")
    gmap = (loc.get("googleMapsUrl") or "").strip()

    series = series_of(apps)
    real_series = [s for s in series if is_real_series(s)]
    headline_series = real_series[0] if real_series else (series[0] if series else "")
    series_txt = "・".join(series)

    canonical = f"{BASE}spot/{lid}/"
    map_url = f"{BASE}?spot={lid}"

    # ── title / description（アプリ側 setSpotTitle と同じ体裁 + タイ語一文）──
    title = name + (f" — {headline_series} ロケ地 / Filming Location" if headline_series else "") + " | Thai Series Map"
    desc = (
        name
        + (f"（{address}）" if address else "")
        + "はタイドラマ・タイGL"
        + (f"「{series_txt}」" if series_txt else "")
        + "のロケ地・聖地です。Googleマップでそのままナビ。"
        + "Filming location of Thai GL series"
        + (f" {series_txt}" if series_txt else "")
        + "."
        + (f" สถานที่ถ่ายทำซีรีส์วาย {series_txt}." if series_txt else " สถานที่ถ่ายทำซีรีส์วาย.")
    )

    # ── Googleマップ導線 ──
    if gmap:
        nav_url = gmap
    elif lat is not None and lng is not None:
        nav_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
    else:
        nav_url = "https://www.google.com/maps/search/?api=1&query=" + esc(name)

    # ── 可視コンテンツ：シーン説明（作品ごと）──
    scene_lines = []
    for s in series:
        scenes = []
        for a in apps:
            if (a.get("series") or "").strip() == s:
                sc = (a.get("scene_desc") or "").strip()
                if sc and sc not in scenes:
                    scenes.append(sc)
        if scenes:
            scene_lines.append(
                f'<div class="app"><div class="app-series">{esc(s)}</div>'
                + "".join(f'<div class="app-scene">{esc(sc)}</div>' for sc in scenes)
                + "</div>"
            )
        else:
            scene_lines.append(f'<div class="app"><div class="app-series">{esc(s)}</div></div>')
    scenes_html = "\n".join(scene_lines)

    # ── 同じ作品のロケ地（内部リンク）──
    related_ids = []
    for s in real_series:
        for rid in locs_by_series.get(s, []):
            if rid != lid and rid not in related_ids and name_by_id.get(rid):
                related_ids.append(rid)
    related_ids = related_ids[:8]
    related_html = ""
    if related_ids:
        lis = "\n".join(
            f'<li><a href="{BASE}spot/{esc(rid)}/">{esc(name_by_id[rid])}</a></li>' for rid in related_ids
        )
        rel_label = esc(real_series[0]) if real_series else ""
        related_html = (
            f'<section class="related"><h2>同じ作品のロケ地'
            + (f"（{rel_label} ほか）" if rel_label else "")
            + f'</h2><ul>{lis}</ul></section>'
        )

    # ── タグ ──
    tags = []
    for s in series:
        tags.append(f'<span class="tag">{esc(s)}</span>')
    if category:
        tags.append(f'<span class="tag tag-cat">{esc(category)}</span>')
    tags_html = "".join(tags)

    # ── 構造化データ（TouristAttraction）──
    ld = {
        "@context": "https://schema.org",
        "@type": "TouristAttraction",
        "name": name,
        "description": desc,
        "url": canonical,
        "isPartOf": {"@type": "WebSite", "name": "Thai Series Map", "url": BASE},
    }
    if address:
        ld["address"] = {"@type": "PostalAddress", "streetAddress": address}
    if lat is not None and lng is not None:
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": lat, "longitude": lng}
    if gmap:
        ld["hasMap"] = gmap
    ld["image"] = BASE + "og-image.png"
    ld_json = json.dumps(ld, ensure_ascii=False)

    breadcrumb_cat = f' <span aria-hidden="true">›</span> {esc(category)}' if category else ""

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{attr(desc)}">
<meta name="robots" content="index,follow,max-image-preview:large">
<link rel="canonical" href="{attr(canonical)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Thai Series Map">
<meta property="og:title" content="{attr(title)}">
<meta property="og:description" content="{attr(desc)}">
<meta property="og:url" content="{attr(canonical)}">
<meta property="og:image" content="{BASE}og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ja_JP">
<meta property="og:locale:alternate" content="en_US">
<meta property="og:locale:alternate" content="th_TH">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">{ld_json}</script>
<meta name="theme-color" content="#2D2A4A">
<link rel="icon" type="image/png" sizes="192x192" href="{BASE}icon-192.png">
<link rel="apple-touch-icon" href="{BASE}apple-touch-icon.png">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700;900&family=Shippori+Mincho:wght@700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--ink:#2D2A4A;--ink-soft:#413D66;--needle:#D6455D;--text:#232138;--sub:#726F8E;--bg:#F7F7FA;--line:#E9E8F1}}
body{{font-family:'Noto Sans JP',sans-serif;color:var(--text);background:var(--bg);line-height:1.7;-webkit-font-smoothing:antialiased}}
a{{color:var(--ink-soft)}}
.wrap{{max-width:720px;margin:0 auto;padding:0 16px 64px}}
header.site{{background:var(--ink);color:#fff}}
header.site .wrap{{padding:14px 16px;display:flex;align-items:center;gap:8px}}
header.site a{{color:#fff;text-decoration:none;font-weight:900;letter-spacing:.02em}}
header.site .logo{{font-size:18px}}
nav.crumb{{font-size:12px;color:var(--sub);padding:14px 0 4px}}
nav.crumb a{{color:var(--sub);text-decoration:none}}
h1{{font-family:'Shippori Mincho','Noto Sans JP',serif;font-size:26px;line-height:1.35;margin:8px 0 12px;color:var(--ink)}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 14px}}
.tag{{font-size:12px;font-weight:700;color:#555;background:#F3F4F6;border:1px solid var(--line);border-radius:999px;padding:4px 10px}}
.tag-cat{{color:var(--ink);background:#EFEEF6;border-color:#D9D6EC}}
.addr{{font-size:14px;color:var(--sub);margin:0 0 16px}}
.memo{{background:#FFFDF5;border:1px solid #F0E7C6;border-radius:10px;padding:10px 12px;font-size:14px;margin:0 0 16px}}
.btns{{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 8px}}
.btn{{flex:1 1 200px;text-align:center;text-decoration:none;font-weight:700;border-radius:12px;padding:14px 16px;font-size:15px}}
.btn-primary{{background:linear-gradient(135deg,var(--ink-soft),var(--ink));color:#fff}}
.btn-map{{background:#fff;color:var(--ink);border:1.5px solid var(--line)}}
h2{{font-family:'Shippori Mincho','Noto Sans JP',serif;font-size:18px;margin:28px 0 12px;color:var(--ink)}}
.app{{border:1px solid var(--line);border-left:4px solid var(--ink-soft);background:#fff;border-radius:10px;padding:12px 14px;margin:0 0 10px}}
.app-series{{font-weight:700;color:var(--ink);margin-bottom:4px}}
.app-scene{{font-size:14px;color:#444}}
.related ul{{list-style:none;display:flex;flex-wrap:wrap;gap:8px;padding:0}}
.related li a{{display:inline-block;font-size:13px;font-weight:700;text-decoration:none;background:#fff;border:1px solid var(--line);border-radius:999px;padding:6px 12px}}
footer.site{{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;font-size:13px;color:var(--sub)}}
footer.site a{{color:var(--ink-soft)}}
footer .intl{{margin-top:8px;font-size:12px;color:var(--sub)}}
</style>
</head>
<body>
<header class="site"><div class="wrap"><a href="{BASE}"><span class="logo">🧭</span> Thai Series Map</a></div></header>
<div class="wrap">
<nav class="crumb"><a href="{BASE}">ホーム</a>{breadcrumb_cat} <span aria-hidden="true">›</span> {esc(name)}</nav>
<h1>{esc(name)}</h1>
<div class="tags">{tags_html}</div>
{f'<p class="addr">📌 {esc(address)}</p>' if address else ''}
{f'<p class="memo">💡 {esc(memo)}</p>' if memo else ''}
<div class="btns">
<a class="btn btn-primary" href="{attr(map_url)}">🗺 インタラクティブ地図で開く</a>
<a class="btn btn-map" href="{attr(nav_url)}" target="_blank" rel="noopener">📍 Googleマップでナビ</a>
</div>
{('<h2>登場作品・シーン</h2>' + scenes_html) if scenes_html else ''}
{related_html}
<footer class="site">
<p><a href="{BASE}">← 聖地巡礼マップのトップへ</a></p>
<p class="intl">Filming location of Thai GL / Thai drama series. สถานที่ถ่ายทำซีรีส์ไทย/วาย — เปิดแผนที่แบบอินเทอร์แอกทีฟได้ที่หน้าแรก</p>
</footer>
</div>
</body>
</html>
"""


def write_sitemap(ids):
    today = datetime.date.today().isoformat()
    urls = [
        f'  <url><loc>{BASE}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>'
    ]
    for lid in ids:
        urls.append(
            f'  <url><loc>{BASE}spot/{lid}/</loc><lastmod>{today}</lastmod><changefreq>monthly</changefreq></url>'
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"🔎 sitemap.xml を生成しました（{len(urls)} URL・/spot/<id>/ 形式）")


if __name__ == "__main__":
    build()
