#!/usr/bin/env python3
"""
Geocode missing lat/lng in data.json using Nominatim (OpenStreetMap).
Usage:
  python3 scripts/geocode.py --input data.json --output data_geocoded.json --delay 1.0

Notes:
- Respects Nominatim usage: include a User-Agent and 1s delay between requests.
- Does NOT overwrite original file; writes a new output file and a timestamped backup of the original.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search'
USER_AGENT = 'thai-series-map-geocoder/1.0 (github.com/cooorrrrry9999)'


def nominatim_search(query):
    params = {
        'q': query,
        'format': 'json',
        'limit': 1,
        'addressdetails': 0,
    }
    url = NOMINATIM_URL + '?' + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode('utf-8')
            results = json.loads(body)
            if results:
                return results[0]
    except Exception as e:
        print('  [ERROR] Nominatim request failed:', e)
    return None


def build_query(loc):
    # prefer address, then name
    parts = []
    if loc.get('address'):
        parts.append(loc.get('address'))
    if loc.get('name') and loc.get('name') not in (loc.get('address') or ''):
        parts.append(loc.get('name'))
    # small fallback to memo
    if not parts and loc.get('memo'):
        parts.append(loc.get('memo'))
    return ', '.join(parts) if parts else loc.get('name','')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='data.json')
    p.add_argument('--output', '-o', default='data_geocoded.json')
    p.add_argument('--delay', '-d', type=float, default=1.0, help='Seconds between requests (Nominatim policy: >=1s)')
    p.add_argument('--limit', type=int, default=None, help='Limit number of locations to geocode (for testing)')
    args = p.parse_args()

    if not os.path.exists(args.input):
        print('Input file not found:', args.input)
        sys.exit(1)

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    locations = data.get('locations', [])
    total = len(locations)
    to_geocode = []
    for loc in locations:
        lat = loc.get('lat')
        lng = loc.get('lng')
        if lat in (None, '', 0) or lng in (None, '', 0):
            to_geocode.append(loc)

    if args.limit:
        to_geocode = to_geocode[:args.limit]

    print(f'Total locations: {total}, missing coordinates: {len(to_geocode)}')
    if not to_geocode:
        print('Nothing to geocode. Exiting.')
        sys.exit(0)

    # backup original
    bak_name = args.input + '.bak.' + datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    with open(bak_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print('Backed up original to', bak_name)

    count_ok = 0
    count_fail = 0
    for idx, loc in enumerate(to_geocode, 1):
        q = build_query(loc)
        print(f'[{idx}/{len(to_geocode)}] Querying: "{q}"')
        if not q:
            print('  [SKIP] No query text available')
            count_fail += 1
            continue
        res = nominatim_search(q)
        if res and res.get('lat') and res.get('lon'):
            lat = float(res['lat'])
            lon = float(res['lon'])
            loc['lat'] = lat
            loc['lng'] = lon
            loc['geocoded'] = True
            loc['geocoded_source'] = 'nominatim'
            loc['geocoded_at'] = datetime.utcnow().isoformat() + 'Z'
            print(f'  [OK] {lat},{lon}')
            count_ok += 1
        else:
            print('  [FAIL] No result')
            count_fail += 1
        time.sleep(args.delay)

    # write output
    out_path = args.output
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Wrote updated data to {out_path} (ok={count_ok}, fail={count_fail})')


if __name__ == '__main__':
    main()
