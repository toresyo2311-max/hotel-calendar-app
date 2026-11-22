#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 중올플(china 289곳) + ③ 아코르(domestic 265곳) → ② 아코르 통합 탭(536곳).

2026-11-22 한진님 지시 — ② 중올플과 ③ 아코르를 하나의 「② 아코르」 탭으로 합친다.

하는 일
  1. 두 탭에 함께 있던 **같은 호텔 18곳**을 한 카드로 합친다.
       · `china` 카드의 alsoIn 이 가리키는 `domestic` 카드를 기준으로 삼아
         (domestic 카드 id 유지 — ① 호텔럭스 alsoIn·SNU 표·프로그램 기대값이 이 id 를 쓴다)
       · 중국 카드에만 있던 `accor`(APC 참여) · `accor_apc` · `accor_apc_t` · `nameZh` 를 옮기고
       · 요금(`rates`)은 날짜마다 **값이 있는 쪽**을 쓴다(중국 카드는 현금 미수집 null, 아코르 카드는 365일 값).
         두 쪽에 모두 값이 있는데 다르면 실패한다 — 조용히 한쪽을 버리지 않는다.
       · alsoIn 은 남은 쪽(① 호텔럭스)만 남긴다.  탭 사이 중복 연결은 통합으로 사라진다.
  2. 남은 china 271 + domestic 265 = **536곳**을 group `accor` 하나로 묶고,
     화면 지역 칩이 쓰는 `zone` 을 단다.
       cn  = 중국(APC) — APC 참여 카드(271) + 아코르 카드 가운데 중국 호텔(20)
       kr  = 국내(한국) 30 · sea = 동남아(태국·베트남·싱가포르) 196 · etc = 기타 해외 19
  3. counts(호텔·칸·요금·레드핫)를 다시 계산하고, 갱신 이력(extended)에 이 작업을 적는다.
  4. 사라지는 중국 카드 id → 남은 카드 id 매핑을 `data/id_alias_accor.json` 에 남긴다
     (index.html 의 옛 #hotel= 링크·즐겨찾기 호환용).

실행 (저장소 루트에서):
    python3 tools/merge_accor_unified_20261122.py            # master_db.json 수정
    python3 tools/merge_accor_unified_20261122.py --dry-run  # 확인만
"""
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
ALIAS = os.path.join(ROOT, 'data', 'id_alias_accor.json')
HIST = os.path.join(ROOT, 'data', 'history', 'hotels')

NOTE = ('2026-11-22 KST ② 아코르 통합 — ② 중올플 289곳과 ③ 아코르 265곳 가운데 같은 호텔 18곳을 '
        '한 카드로 합쳐 536곳(중국(APC) 291 · 국내 30 · 동남아 196 · 기타 해외 19)으로 정리했습니다. '
        'APC 무료숙박·권역·약관 제외일은 중국(APC) 지역/APC 모드에서만 보이고, '
        '1박 최저가·Stay Plus·Red Hot Rooms 는 한 화면에서 고를 수 있습니다.')

SEA_REGIONS = ('태국', '베트남', '싱가포르')


def zone_of(h):
    if h.get('accor'):
        return 'cn'
    region = str(h.get('region') or '')
    if region == '한국':
        return 'kr'
    if region in SEA_REGIONS:
        return 'sea'
    if region == '중국':
        return 'cn'
    return 'etc'


def merge_rates(dom, chi):
    """날짜별로 값이 있는 쪽을 쓴다. 양쪽에 값이 있는데 다르면 실패."""
    a = dom.get('rates') or {}
    b = chi.get('rates') or {}
    keys = sorted(set(a) | set(b))
    out = {}
    conflicts = []
    for d in keys:
        va, vb = a.get(d), b.get(d)
        if va is not None and vb is not None and va != vb:
            conflicts.append((d, va, vb))
        out[d] = va if va is not None else vb
    return out, conflicts


def merge_history(alias, dry=False):
    """data/history/hotels — 사라진 카드의 가격 이력을 남은 카드로 합치고 파일을 지운다."""
    if not os.path.isdir(HIST):
        return 0
    moved = 0
    for gone, keep in sorted(alias.items()):
        src = os.path.join(HIST, gone + '.json')
        dst = os.path.join(HIST, keep + '.json')
        if not os.path.exists(src):
            continue
        with open(src, encoding='utf-8') as fp:
            a = json.load(fp)
        if os.path.exists(dst):
            with open(dst, encoding='utf-8') as fp:
                b = json.load(fp)
            if a.get('schema') != b.get('schema'):
                raise SystemExit('%s ↔ %s history schema 가 다릅니다.' % (gone, keep))
            sa, sb = a.get('series') or {}, b.get('series') or {}
            for d, rows in sa.items():
                cur = sb.setdefault(d, [])
                seen = {tuple(r) for r in cur}
                for row in rows:
                    if tuple(row) not in seen:
                        cur.append(row)
                        seen.add(tuple(row))
                cur.sort(key=lambda r: r[0])
            b['updated'] = max(str(a.get('updated') or ''), str(b.get('updated') or ''))
            b.setdefault('srcs', [])
            for x in (a.get('srcs') or []):
                if x not in b['srcs']:
                    b['srcs'].append(x)
            out = b
        else:
            # 남은 카드의 이력이 없으면 사라진 카드의 이력을 그대로 이어받는다
            a['id'] = keep
            out = a
        if not dry:
            tmp = dst + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fp:
                json.dump(out, fp, ensure_ascii=False, separators=(',', ':'))
                fp.write('\n')
            os.replace(tmp, dst)
            os.remove(src)
        moved += 1
    # 남은 ② 아코르 카드의 history group 표기를 통합 탭으로 맞춘다
    fixed = 0
    if not dry:
        with open(MASTER, encoding='utf-8') as fp:
            master = json.load(fp)
        by_id = {h['id']: h for h in master['hotels'] if h.get('group') == 'accor'}
        for name in sorted(os.listdir(HIST)):
            if not name.endswith('.json'):
                continue
            hid = name[:-5]
            h = by_id.get(hid)
            if not h:
                continue
            path = os.path.join(HIST, name)
            with open(path, encoding='utf-8') as fp:
                obj = json.load(fp)
            if obj.get('group') == 'accor' and obj.get('zone') == h.get('zone'):
                continue
            obj['group'] = 'accor'
            obj['zone'] = h.get('zone')
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as fp:
                json.dump(obj, fp, ensure_ascii=False, separators=(',', ':'))
                fp.write('\n')
            os.replace(tmp, path)
            fixed += 1
    print('history — 합친 카드 %d개 · group/zone 표기 정리 %d개' % (moved, fixed))
    return moved


def main(argv):
    dry = '--dry-run' in argv
    with open(MASTER, encoding='utf-8') as fp:
        db = json.load(fp)
    hotels = db['hotels']
    by_id = {h['id']: h for h in hotels}

    chi = [h for h in hotels if h.get('group') == 'china']
    dom = [h for h in hotels if h.get('group') == 'domestic']
    if not chi or not dom:
        # 이미 통합된 파일 — 이력(data/history)만 정리하고 끝낸다
        alias_path = ALIAS
        alias = json.loads(open(alias_path, encoding='utf-8').read()).get('map') or {}
        merge_history(alias, dry)
        print('이미 통합된 파일입니다 (china %d · domestic %d) — 이력만 정리했습니다.' % (len(chi), len(dom)))
        return 0

    alias = {}
    drop = set()
    merged = 0
    for c in chi:
        other = c.get('alsoIn')
        if not other or other not in by_id:
            continue
        d = by_id[other]
        if d.get('group') != 'domestic':
            raise SystemExit('%s 의 alsoIn %s 가 아코르 카드가 아닙니다.' % (c['id'], other))
        if d.get('alsoIn') != c['id']:
            raise SystemExit('%s ↔ %s alsoIn 이 한쪽만 있습니다.' % (c['id'], other))
        rates, conflicts = merge_rates(d, c)
        if conflicts:
            raise SystemExit('%s ↔ %s 요금 충돌 %d칸 (예: %s)' % (c['id'], other, len(conflicts), conflicts[:3]))
        for k in ('id', 'group', 'alsoIn', 'alsoInLabel'):
            pass
        # 중국 카드에만 있는 값 — 손실 없이 옮긴다
        if c.get('accor'):
            d['accor'] = c['accor']
        if c.get('accor_apc'):
            d['accor_apc'] = c['accor_apc']
        if c.get('accor_apc_t'):
            d['accor_apc_t'] = c['accor_apc_t']
        if c.get('nameZh'):
            d['nameZh'] = c['nameZh']
        if c.get('blackouts'):
            d['blackouts'] = sorted(set(d.get('blackouts') or []) | set(c['blackouts']))
        if c.get('english') and not d.get('english'):
            d['english'] = c['english']
        if c.get('brand') and not d.get('brand'):
            d['brand'] = c['brand']
        if c.get('city') and not d.get('city'):
            d['city'] = c['city']
        d['rates'] = rates
        # 출처는 두 쪽을 모두 남긴다 — 나중에 어느 조사값인지 확인할 수 있게
        src_d = str(d.get('source') or '').strip()
        src_c = str(c.get('source') or '').strip()
        if src_c and src_c not in src_d:
            d['source'] = (src_d + ' / ' + src_c) if src_d else src_c
        if c.get('promotion'):
            p_d = str(d.get('promotion') or '').strip()
            if c['promotion'] not in p_d:
                d['promotion'] = (p_d + ' · ' + c['promotion']) if p_d else c['promotion']
        # alsoIn 은 남은 쪽(① 호텔럭스 등)만 남긴다
        if d.get('alsoIn') == c['id']:
            d.pop('alsoIn', None)
            d.pop('alsoInLabel', None)
        alias[c['id']] = d['id']
        drop.add(c['id'])
        merged += 1

    if merged != 18:
        raise SystemExit('합친 호텔이 %d곳입니다 (기대 18곳) — 그대로 멈춥니다.' % merged)

    out = []
    for h in hotels:
        if h['id'] in drop:
            continue
        if h.get('group') in ('china', 'domestic'):
            h['group'] = 'accor'
            h['zone'] = zone_of(h)
        out.append(h)

    rank = {'kr': 0, 'sea': 1, 'cn': 2, 'etc': 3}
    lux = [h for h in out if h.get('group') == 'lux']
    accor = [h for h in out if h.get('group') == 'accor']
    mar = [h for h in out if h.get('group') == 'marriott']
    accor.sort(key=lambda h: (rank.get(h.get('zone'), 9), str(h.get('city') or ''), str(h.get('name') or '')))
    db['hotels'] = lux + accor + mar

    # counts 다시 계산 (tools/master_db.py stats_of 와 같은 정의)
    hotels = db['hotels']
    cells = sum(len(h.get('rates') or {}) for h in hotels)
    priced = sum(1 for h in hotels for v in (h.get('rates') or {}).values() if v is not None)
    tabs = {}
    for h in hotels:
        tabs[h.get('group')] = tabs.get(h.get('group'), 0) + 1
    flights = db.get('flights') or {}
    routes = flights.get('routes') or []
    deals = sum(len(r.get('deals') or []) for r in routes)
    tt = db.get('ttang') or {}
    cnt = db.get('counts') or {}
    cnt.update({
        'hotels': len(hotels),
        'tabs': tabs,
        'cells': cells,
        'priced': priced,
        'na': cells - priced,
        'stayplus': sum(len(h.get('stayplus2') or {}) + len(h.get('stayplus3') or {}) for h in hotels),
        'routes': len(routes),
        'deals': deals,
        'snu': len(((db.get('accor') or {}).get('rows')) or []),
        'pus_deals': len((tt.get('deals') or [])),
        'pus_routes': len({d.get('code') for d in (tt.get('deals') or [])}),
        'redhot_hotels': sum(1 for h in hotels if h.get('redhot')),
        'redhot_cells': sum(len(h.get('redhotRates') or {}) for h in hotels),
    })
    db['counts'] = cnt
    db['generated_at'] = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    ext = str(db.get('extended') or '')
    if NOTE not in ext:
        db['extended'] = (ext + ' / ' + NOTE) if ext else NOTE

    zones = {}
    for h in accor:
        zones[h.get('zone')] = zones.get(h.get('zone'), 0) + 1
    print('합친 호텔 %d곳 · 삭제한 중국 카드 %d장' % (merged, len(drop)))
    print('통합 ② 아코르 %d곳 · 지역 %s' % (len(accor), zones))
    print('탭 %s' % tabs)
    print('칸 %d · 요금 %d · SNU %d · 레드핫 %d곳/%d칸' % (
        cells, priced, cnt['snu'], cnt['redhot_hotels'], cnt['redhot_cells']))

    if dry:
        print('--dry-run — 파일을 쓰지 않았습니다.')
        return 0

    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(db, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    with open(ALIAS, 'w', encoding='utf-8') as fp:
        json.dump({'note': '2026-11-22 ② 아코르 통합 — 사라진 ② 중올플 카드 id → 통합 카드 id',
                   'map': alias}, fp, ensure_ascii=False, indent=1, sort_keys=True)
        fp.write('\n')
    print('wrote %s' % os.path.relpath(MASTER, ROOT))
    print('wrote %s (%d개)' % (os.path.relpath(ALIAS, ROOT), len(alias)))
    merge_history(alias)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
