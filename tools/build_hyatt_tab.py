#!/usr/bin/env python3
"""Build data/app/tab10_hyatt.json from hyatt-apac-master.json, group1~4 JSONs, and tab1_vip.json."""
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
MASTER_PATH = os.path.join(WS, 'hotel_research', 'hyatt-apac-master.json')
GROUP_PATHS = [
    os.path.join(WS, 'hotel_research', f'hyatt-apac-group{i}.json')
    for i in range(1, 5)
]
VIP_PATH = os.path.join(ROOT, 'data', 'app', 'tab1_vip.json')
OUT_PATH = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')

START = date(2026, 12, 1)
END = date(2027, 11, 30)
DATES = []
cur = START
while cur <= END:
    DATES.append(cur.isoformat())
    cur += timedelta(days=1)


def unpack_compact(obj):
    if not isinstance(obj, dict):
        return obj or {}
    if '$d' in obj and '$v' in obj:
        base = date.fromisoformat(obj['$d'])
        return {(base + timedelta(days=i)).isoformat(): v for i, v in enumerate(obj['$v']) if v is not None}
    if '$t' in obj and '$r' in obj:
        t = obj['$t']
        r = obj['$r']
        return {d: r[i] for i, d in enumerate(t) if i < len(r) and r[i] is not None}
    return {k: v for k, v in obj.items() if len(k) == 10 and v is not None}


def pack_compact(m):
    if not m:
        return None
    cleaned = {}
    for d in DATES:
        v = m.get(d)
        if isinstance(v, (int, float)) and v > 0:
            cleaned[d] = int(round(v))
    if not cleaned:
        return None
    return {'$d': DATES[0], '$v': [cleaned.get(d) for d in DATES]}


def main():
    with open(MASTER_PATH, 'r', encoding='utf-8') as f:
        master = json.load(f)['hotels']

    vip_map = {}
    if os.path.exists(VIP_PATH):
        with open(VIP_PATH, 'r', encoding='utf-8') as f:
            vip_data = json.load(f)
            vh = vip_data.get('hotels', [])
            if isinstance(vh, dict) and '$t' in vh and '$r' in vh:
                cols = vh['$t']
                vh = [dict(zip(cols, row)) for row in vh['$r']]
            for h in vh:
                vip_map[h['id']] = h

    group_by_id = {}
    group_by_code = {}
    for gp in GROUP_PATHS:
        if not os.path.exists(gp):
            print(f'[skip] missing {gp}')
            continue
        with open(gp, 'r', encoding='utf-8') as f:
            gd = json.load(f)
        items = gd.get('hotels', gd) if isinstance(gd, dict) else gd
        if isinstance(items, dict):
            items = list(items.values())
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('id'):
                group_by_id[item['id']] = item
            if item.get('code'):
                group_by_code[item['code'].lower()] = item

    out_hotels = []
    for m in master:
        hid = m['id']
        code = m['code'].lower()
        g = group_by_id.get(hid) or group_by_code.get(code) or {}
        actual_code = (g.get('code') or code).lower()
        vip = vip_map.get(m.get('vip_id')) if m.get('vip_id') else None

        pts_raw = unpack_compact(g.get('points'))
        off_raw = unpack_compact(g.get('cash_official'))
        hlx_raw = unpack_compact(g.get('cash_hotelux'))
        if not hlx_raw and vip:
            hlx_raw = unpack_compact(vip.get('rates'))

        vip_url = None
        if vip:
            vip_url = (vip.get('links') or {}).get('official') or vip.get('url')
            if not vip_url and vip.get('ref_id'):
                vip_url = f"https://hotel.hotelux.com/hotelDetail/{vip['ref_id']}"
        if not vip_url:
            vip_url = g.get('hotelux_url')
            if not vip_url and g.get('hotelux_id'):
                vip_url = f"https://hotel.hotelux.com/hotelDetail/{g['hotelux_id']}"

        h_obj = {
            'id': hid,
            'group': 'hyatt',
            'code': actual_code,
            'region': m['region'],
            'city': m['city'],
            'name': m['name'],
            'english': m['english'],
            'brand': '하얏트',
            'category': g.get('category') or g.get('award_category') or g.get('award_category_official'),
            'vip_id': m.get('vip_id'),
            'alsoIn': m.get('vip_id'),
            'hlx_in': bool(hlx_raw or vip_url),
            'points': pack_compact(pts_raw) or {'$d': DATES[0], '$v': [None] * len(DATES)},
            'rates_official': pack_compact(off_raw),
            'rates_hlx': pack_compact(hlx_raw),
            'links': {
                'official': f'https://www.hyatt.com/shop/rooms/{actual_code}',
                'hlx': vip_url
            },
            'promotion': (vip.get('promotion') if vip else None) or g.get('promotion'),
            'note': g.get('note')
        }
        out_hotels.append(h_obj)

    payload = {
        'group': 'hyatt',
        'generated_at': date.today().isoformat(),
        'window': ['2026-12-01', '2027-11-30'],
        'hotels': out_hotels
    }
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    pts_cnt = sum(1 for h in out_hotels if any(x is not None for x in h['points']['$v']))
    off_cnt = sum(1 for h in out_hotels if h['rates_official'] is not None)
    hlx_cnt = sum(1 for h in out_hotels if h['rates_hlx'] is not None)
    print(f'Wrote {OUT_PATH}: {len(out_hotels)} hotels (points={pts_cnt}, official={off_cnt}, hlx={hlx_cnt})')


if __name__ == '__main__':
    main()
