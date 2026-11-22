#!/usr/bin/env python3
"""④ 하얏트 — 유럽 2차 프랑스 14 · 독일 25 = 39곳(365일 아워드 포인트) 병합 (2026-11-23)

입력  : memory/clones/06130525-jin489/pickle/2026-11-23-0447/received/0-hyatt-eu-frde39-bundle.json
        (meta: EU-FRDE-39 · window 2026-12-01~2027-11-30 · priced_cells 12284)
대상  : data/app/tab10_hyatt.json  (hy01~hy236 → hy237~hy275, 총 275곳)

- 기존 236곳은 값·순서 그대로 보존(원본 객체 동일성 검사)
- 번들 스키마(code·name·country·city·region·award_category·brand·official_url·points)를
  tab10_hyatt.json 키 순서(id, group, code, region, city, name, english, brand, category,
  vip_id, alsoIn, hlx_in, points, rates_official, rates_hlx, links, promotion, note)로 변환
- city 는 앞뒤 공백·겹공백·비가시 문자를 정리한다(이번 번들은 정리할 값이 없음을 확인)
- points 는 {"$d":"2026-12-01","$v":[365개]} 로 변환, null 은 보간 없이 유지
- ① 호텔럭스(tab1_vip.json 161곳) 코드·영문명·국문명·도시 전수 대조 후 겹치면
  vip_id/alsoIn/hlx_in/links.hlx 연결
"""
import json, copy, unicodedata
from datetime import date, timedelta

BASE = '/workspace'
BUNDLE = f'{BASE}/memory/clones/06130525-jin489/pickle/2026-11-23-0447/received/0-hyatt-eu-frde39-bundle.json'
TAB = f'{BASE}/work/hotel-calendar-app/data/app/tab10_hyatt.json'
VIP = f'{BASE}/work/hotel-calendar-app/data/app/tab1_vip.json'

# 도시 묶음 순서 — 같은 도시를 붙여 두어 도시 필터에서 목록이 흩어지지 않게 한다.
# 프랑스(파리 → 니스 → 칸 → 비아리츠 → 보르도 → 랭스 → 루앙 → 툴루즈 → CDG) → 독일(베를린 → 뮌헨 →
# 프랑크푸르트 → 에쉬보른 → 쾰른 → 뒤셀도르프 → 함부르크 → 하노버 → 킬 → 라이프치히 → 마인츠 → 울름)
CITY_ORDER = [
    'Paris', 'Nice', 'Cannes', 'Biarritz', 'Bordeaux', 'Reims', 'Rouen', 'Toulouse', 'Roissy-en-France',
    'Berlin', 'Munich', 'Frankfurt am Main', 'Eschborn', 'Cologne', 'Dusseldorf',
    'Hamburg', 'Hanover', 'Kiel', 'Leipzig', 'Mainz', 'Ulm',
]

bundle = json.load(open(BUNDLE, encoding='utf-8'))
tab = json.load(open(TAB, encoding='utf-8'))
before = copy.deepcopy(tab['hotels'])
assert len(before) == 236, len(before)
assert len(bundle['hotels']) == 39, len(bundle['hotels'])

w0 = date(2026, 12, 1)
days = [(w0 + timedelta(days=i)).isoformat() for i in range(365)]

def clean_city(s):
    s = unicodedata.normalize('NFC', str(s or ''))
    # 비가시 문자(제로폭·NBSP 등)를 보통 공백으로 바꾸고 겹공백을 하나로
    s = ''.join(' ' if (ch.isspace() or unicodedata.category(ch) in ('Cf', 'Cc')) else ch for ch in s)
    return ' '.join(s.split())

# ── ① 호텔럭스 대조용 색인 ──────────────────────────────────────
vip = json.load(open(VIP, encoding='utf-8'))
cols = vip['hotels']['$t']
vip_rows = [dict(zip(cols, r)) for r in vip['hotels']['$r']]
def norm(s):
    return ' '.join(str(s or '').lower().replace('’', "'").replace('–', '-').replace('—', '-').split())
vip_by_name = {}
vip_by_city = {}
for r in vip_rows:
    for k in ('english', 'name'):
        if r.get(k):
            vip_by_name.setdefault(norm(r[k]), r)
    if r.get('city'):
        vip_by_city.setdefault(norm(r['city']), []).append(r)
vip_by_code = {str(r.get('ref_id') or '').strip(): r for r in vip_rows if r.get('ref_id')}

hotels = sorted(bundle['hotels'].values(), key=lambda h: (CITY_ORDER.index(clean_city(h['city'])), h['name']))
assert len(hotels) == 39

added, report = [], []
for i, src in enumerate(hotels, start=237):
    hid = f'hy{i:02d}'
    city = clean_city(src['city'])
    pts = [src['points'].get(d) for d in days]
    assert len(src['points']) == 365, (src['code'], len(src['points']))
    # ① 호텔럭스 겹침 확인 — 코드 · 영문명 · 국문명(이름이 같은 경우)
    hit = vip_by_code.get(src['code'])
    if not hit:
        hit = vip_by_name.get(norm(src['name']))
    priced = sum(1 for v in pts if v is not None)
    if priced == 0:
        note = ('스탠다드 아워드 365일 실측(2026-11-23 · hyatt.com) — 365일 모두 값이 없습니다(0일). '
                '재고 없음·예약창 밖·미조회를 구분하지 않음(NA). 공홈 현금가 미수집.')
    else:
        note = (f'스탠다드 아워드 365일 실측(2026-11-23 · hyatt.com) — 포인트 {priced}일 · '
                f'값 없는 {365 - priced}일은 재고 없음·예약창 밖·미조회를 구분하지 않음(NA). 공홈 현금가 미수집.')
    obj = {
        'id': hid,
        'group': 'hyatt',
        'code': src['code'],
        'region': '유럽',
        'city': city,
        'name': str(src['name']).strip(),
        'english': str(src['name']).strip(),
        'brand': src['brand'],
        'category': src['award_category'],   # 원본 전부 null — 숫자로 만들지 않는다
        'vip_id': hit['id'] if hit else None,
        'alsoIn': hit['id'] if hit else None,
        'hlx_in': bool(hit),
        'points': {'$d': '2026-12-01', '$v': pts},
        'rates_official': None,
        'rates_hlx': None,
        'links': {'official': src['official_url'], 'hlx': None},
        'promotion': None,
        'note': note,
    }
    if hit:
        obj['links']['hlx'] = hit.get('links', {}).get('hlx') if isinstance(hit.get('links'), dict) else None
        report.append((hid, src['code'], src['name'], city, priced, f"①{hit['id']}"))
    else:
        report.append((hid, src['code'], src['name'], city, priced, ''))
    added.append(obj)

assert len(added) == 39
assert [h['id'] for h in added] == [f'hy{i:02d}' for i in range(237, 276)]
old_codes = {h['code'] for h in before}
dup = [h['code'] for h in added if h['code'] in old_codes]
assert not dup, dup
assert len({h['code'] for h in added}) == 39

tab['hotels'] = before + added
tab['generated_at'] = '2026-11-23'

with open(TAB, 'w', encoding='utf-8') as f:
    json.dump(tab, f, ensure_ascii=False, separators=(',', ':'))

print(f'기존 {len(before)} + 신규 {len(added)} = {len(tab["hotels"])}곳')
print(f'{"id":6}{"code":7}{"city":20}{"pt":>5}  name / ①')
for row in report:
    print(f'{row[0]:6}{row[1]:7}{row[3]:20}{row[4]:>5}  {row[2][:56]} {row[5]}')
tot = len(added) * 365
priced = sum(1 for a in added for v in a['points']['$v'] if v is not None)
print(f'신규 셀 {tot} 중 값 {priced} · null {tot - priced} (번들 priced_cells {bundle["meta"]["priced_cells"]})')
print('① 겹침', sum(1 for r in report if r[5]))
