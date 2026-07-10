#!/usr/bin/env python3
"""
data.json クリーンアップ（deploy.sh から自動実行される）

Firestore 側にまだ残っている既知の問題を、公開用 data.json 上で毎回修正する保険。
Firestore 本体が掃除されたら（admin の重複マージ機能で対応予定）このスクリプトは
何もしなくなるだけなので、置いたままで害はない。

やること:
  1. 既知の重複スポット16組の統合（appearances の付け替え・欠損フィールド補完）
  2. appearances の重複解消（同一 場所×作品×タレント の完全重複と空シーンを畳む）
  3. レストラン絵文字 🍖 → 🍽️ の正規化
  4. 個別修正（Renaissance Hotel の誤座標、Wheel Sky のタイポなど）

使い方: python3 scripts/clean_data.py data.json
"""
import json
import sys
import collections

# 統合マップ: 残すID → [消すID, ...]（2026-07-10 時点の Firestore 重複調査より）
MERGE = {
    '0rt1k2YzTnbOyXs9fzBM': ['awqGCyoJEJ0YiHHKgiMi'],   # FRIEND FRIEND
    '1l2EAG7UUKsnoTHCGqr6': ['dTNUK7FfmAZ6DIUzo74u'],   # BAD POUTINE
    '8EQIvnkZoD3p40kj5WJQ': ['Fkb7oDM46Bhjf0SzfGmv'],   # Khao Sam Muk Viewpoint
    'zPsBxzA7801eMJDXs4VK': ['Fqoyl11LfrEz7MRrBAU5'],   # Kraft Kaffe
    'Gfl3ajdpw2R9tPKdzeaw': ['veC78j3KHnW1yFTPN1T7'],   # Nonna & Son Pattaya
    'KPhdVDuGqm3kcrckE4cP': ['yLOVywfmiaoGbAnQtdzO'],   # Luggaw Emsphere
    'LOC032':               ['olCrqJZ106UdVbIl8zZA'],   # D-Sports Stadium
    'SH1h2nzncxyD42pe7bUH': ['uIzcWxPOPLNExzNnOhks'],   # Baan Suan Sathorn Craft & Cafe
    'POvVZjemPq48sEc2blQZ': ['c0g6ifjopMplYuMjU8tg'],   # Thamsuea Party House
    'srNGRXHAkhNv1pGG8SiM': ['oJ6R6mYz8jZKkyY76EEp'],   # Renaissance Bangkok Ratchaprasong
    'rCLAhkQzRkjFVrjRBBB4': ['sEDSJvHi6Fpzksqap0Wl'],   # Colonel Kanit Moo Kata
    '1qZ2PyUGangQgVFzQr90': ['ZPWKJpYWKafTeDCVjBFR'],   # Baan 168 Ram Inthra 117
    'wEbBlXhsTWf50PnrlptW': ['DRApoAu5ULHk7ns0yOHz'],   # Centara Q Resort Rayong
    'LOC014':               ['jB1QStYt4njXJTCymI5b'],   # Wheel Sky (Asiatique)
    'gmcKAdw3cGV6BWoCTFpk': ['Oe3EvVJ3SevfIbwtNqjd'],   # After Yum Pattaya
    'xNAqTWbrATFsRewhYb6m': ['SBY0ij4Bql54gDwbVmUi'],   # Luka cafe
}

# 個別修正: id → {フィールド: 値}
FIXES = {
    'srNGRXHAkhNv1pGG8SiM': {'lat': 13.74251, 'lng': 100.54197},  # 誤ジオコーディング修正
    'LOC014': {'name': 'Wheel Sky（Asiatique）'},                  # タイポ修正
    'SH1h2nzncxyD42pe7bUH': {'category': 'カフェ'},
}

EMOJI_SWAP = {'🍖': '🍽️'}


def main(path):
    with open(path) as f:
        d = json.load(f)
    locs = d.get('locations', [])
    apps = d.get('appearances', [])
    by_id = {l['id']: l for l in locs}
    changed = []

    # 1. 重複統合（存在するIDだけ処理＝Firestore掃除後は自然に何もしなくなる）
    drop2keep = {}
    for keep, drops in MERGE.items():
        if keep not in by_id:
            continue
        for dp in drops:
            if dp in by_id:
                drop2keep[dp] = keep
    for dp, keep in drop2keep.items():
        kl, dl = by_id[keep], by_id[dp]
        for fld in ('address', 'memo', 'googleMapsUrl', 'category'):
            if not kl.get(fld) and dl.get(fld):
                kl[fld] = dl[fld]
    if drop2keep:
        d['locations'] = locs = [l for l in locs if l['id'] not in drop2keep]
        for a in apps:
            if a.get('location_id') in drop2keep:
                a['location_id'] = drop2keep[a['location_id']]
        changed.append(f'重複統合 {len(drop2keep)}件')

    # 2. appearances 重複解消
    groups = collections.defaultdict(list)
    for a in apps:
        groups[(a.get('location_id'), a.get('series'), a.get('cp'))].append(a)
    keep_apps = []
    for items in groups.values():
        seen = set()
        withscene = [x for x in items if (x.get('scene_desc') or '').strip()]
        for a in items:
            sc = (a.get('scene_desc') or '').strip()
            if not sc and withscene:
                continue
            if sc in seen:
                continue
            seen.add(sc)
            keep_apps.append(a)
    if len(keep_apps) != len(apps):
        changed.append(f'紐付け重複解消 {len(apps) - len(keep_apps)}件')
        d['appearances'] = keep_apps

    # 3. 絵文字正規化
    n = 0
    for c in d.get('category_master', []):
        if c.get('emoji') in EMOJI_SWAP:
            c['emoji'] = EMOJI_SWAP[c['emoji']]
            n += 1
    if n:
        changed.append(f'絵文字正規化 {n}件')

    # 4. 個別修正
    n = 0
    for lid, fix in FIXES.items():
        l = by_id.get(lid)
        if l and any(l.get(k) != v for k, v in fix.items()):
            l.update(fix)
            n += 1
    if n:
        changed.append(f'個別修正 {n}件')

    if changed:
        with open(path, 'w') as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        print(f'  クリーンアップ実施: {" / ".join(changed)}（ロケ地 {len(d["locations"])}件）')
    else:
        print('  クリーンアップ対象なし（データはきれいです）')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'data.json')
