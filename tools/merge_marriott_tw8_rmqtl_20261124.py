#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 대만 8차 1곳(RMQTL 알로프트 타이중) 병합 (307 → 308곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `master_db.py inject`).

입력(2026-11-24 6번(@jin_6) 실측 · marriott.com availabilityCalendar + 아워드 포인트 캘린더):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-24-1843/received/0-marriott-wave1-tw-hk-mo-47.json
    — 누적 28곳(28/47곳 완료)
  · 신규는 1곳(RMQTL · 파일 28번째)뿐이다. 위치로 자르지 않고 **기존 정본에 없는 코드**로 고른다
    (중복 추가 금지).

규칙:
  · m308 하나만 메리어트 묶음 맨 뒤에 붙인다. 기존 307곳은 값·순서·alsoIn 그대로.
  · note 는 JSON 실측값 기준으로만 적는다 — 현금 345일 144,424~268,677원 · 결번 20일(3구간),
    포인트 344일 19,000~27,000P · 결번 21일(4구간). 6번 대화에 적힌 「현금 365/365일」은
    실측과 다르므로 원자료 값을 그대로 싣고 보간하지 않는다.
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한다(겹침 0 예상).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-24-1843/received/'
       '0-marriott-wave1-tw-hk-mo-47.json')
DAY = '2026-11-24'
FIRST = 308                       # m308
CODE = 'RMQTL'
EXPECT_SRC = 28                   # 누적 28곳
EXPECT_POS = 28                   # 원본 안 위치(1부터)


def ranges(nulls):
    """null 날짜 목록 -> 연속 구간 문자열 목록."""
    ds = sorted(nulls)
    out = []
    for d in ds:
        dd = datetime.date.fromisoformat(d)
        if out and (dd - out[-1][1]).days == 1:
            out[-1][1] = dd
        else:
            out.append([dd, dd])
    return ['%s~%s' % (a, b) if a != b else str(a) for a, b in out]


def load():
    with open(SRC, encoding='utf-8') as fp:
        doc = json.load(fp)
    if doc['checked_at'] != DAY:
        raise SystemExit('대만 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = doc['hotels']
    if len(hotels) != EXPECT_SRC:
        raise SystemExit('대만 원본 호텔 %d곳 (누적 %d곳이어야 함)' % (len(hotels), EXPECT_SRC))
    pos = {}
    for i, h in enumerate(hotels):
        pos.setdefault(h['code'], []).append(i + 1)
    if pos.get(CODE) != [EXPECT_POS]:
        raise SystemExit('%s 위치 %s (기대 %d번 한 곳)' % (CODE, pos.get(CODE), EXPECT_POS))
    h = hotels[EXPECT_POS - 1]
    if h['country'] != '대만':
        raise SystemExit('%s 국가 %s (대만 이어야 함)' % (h['code'], h['country']))
    return h


def build(h, hid):
    rates, pt_map = h['rates'], h['points']
    for name, vals in (('rates', rates), ('points', pt_map)):
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['code'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['code'], name, d))
    cash_days = sum(1 for v in rates.values() if isinstance(v, (int, float)))
    pt_days = sum(1 for v in pt_map.values() if isinstance(v, int))
    cash_vals = [v for v in rates.values() if isinstance(v, (int, float))]
    pt_vals = [v for v in pt_map.values() if isinstance(v, int)]
    if not cash_vals or not pt_vals:
        raise SystemExit('%s 현금 %d칸 · 포인트 %d칸 — 0칸은 이번 원본에 없어야 함'
                         % (h['code'], cash_days, pt_days))

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    notes.append('현금 (세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))

    cash_gap_days = [d for d, v in rates.items() if not isinstance(v, (int, float))]
    pt_gap_days = [d for d, v in pt_map.items() if not isinstance(v, int)]
    cash_gap = ranges(cash_gap_days)
    pt_gap = ranges(pt_gap_days)
    notes.append('현금 결번 %d일 %d개 구간(%s)' % (
        len(cash_gap_days), len(cash_gap), ' · '.join(cash_gap)))
    notes.append('포인트 결번 %d일 %d개 구간(%s)' % (
        len(pt_gap_days), len(pt_gap), ' · '.join(pt_gap)))
    # 값 분포 — 원자료에서 그대로 센 사실만 적는다
    from collections import Counter
    cash_c = Counter(cash_vals)
    pt_c = Counter(pt_vals)
    cash_rank = ['%s원 %d일' % (format(v, ','), n) for v, n in cash_c.most_common()]
    pt_rank = ['%sP %d일' % (format(v, ','), n) for v, n in pt_c.most_common()]
    notes.append('현금 값은 %s이고, 2027-02-06~02-09 4일 연속 %s원이 창 안 최고가입니다' % (
        ' · '.join(cash_rank[:3]), format(max(cash_vals), ',')))
    notes.append('포인트 값은 %s이고, %sP는 2027-10-25~11-12 19일 연속을 포함해 총 %d일입니다' % (
        ' · '.join(pt_rank[:3]), format(max(pt_vals), ','),
        sum(1 for v in pt_vals if v == max(pt_vals))))
    notes.append('현금·포인트가 함께 2027-11-12 에 끊겨 2027-11-13~11-30 18일이 예약 창 끝'
                 '(Rate Unavailable)입니다')
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    return {
        'id': hid,
        'group': 'marriott',
        'brand': h['brand'],
        'city': h['city'],
        'region': '대만',
        'name': h['name'],
        'english': h['english'],
        'promotion': '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days),
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · 6번 실측 marriott-wave1-tw-hk-mo 대만 8차 1곳 365일'
                   % (DAY, DAY)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def crosscheck_lux(master, h):
    """① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조."""
    lux = [x for x in master['hotels'] if x.get('group') == 'lux']
    lcodes = {x.get('code') for x in lux}
    lenames = {(x.get('english') or '').strip().lower() for x in lux}
    lnames = {x.get('name') for x in lux}
    lcities = {x.get('city') for x in lux}
    hits = []
    if h['code'] in lcodes or h['english'].strip().lower() in lenames or h['name'] in lnames:
        hits.append((h['code'], h['name']))
    return len(lux), hits, sorted(lcities)


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src = load()

    ids = {x['id'] for x in master['hotels']}
    codes = {x.get('code') for x in master['hotels'] if x.get('code')}
    names = {(x.get('english') or '').strip().lower() for x in master['hotels']}
    hid = 'm%d' % FIRST
    if hid in ids:
        raise SystemExit('이미 있는 id: %s' % hid)
    if src['code'] in codes:
        raise SystemExit('이미 있는 code: %s (중복 추가 금지)' % src['code'])
    if src['english'].strip().lower() in names:
        raise SystemExit('이미 있는 영문명: %s' % src['english'])
    new = [build(src, hid)]

    lux_n, lux_hits, lux_cities = crosscheck_lux(master, src)
    print('① 호텔럭스 %d곳 대조 — 겹침 %d곳 %s' % (lux_n, len(lux_hits), lux_hits))
    print('   ① 탭 도시: %s' % ', '.join(lux_cities))
    if lux_hits:
        raise SystemExit('① 탭과 겹치는 호텔이 있습니다 — alsoIn 연결 여부를 먼저 정하세요')

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 307곳 순서 보존
    pos = max(i for i, x in enumerate(master['hotels']) if x.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    src_name = os.path.basename(SRC)
    if src_name not in master['sources']:
        master['sources'].append(src_name)

    card = new[0]
    cash = sum(1 for v in card['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for v in card['points'].values() if isinstance(v, int))
    line = (
        '2026-11-24 KST ③ 메리어트 대만 8차 1곳 병합(307→308곳 · 대만 28 · 통합 1,005곳) — '
        'RMQTL 알로프트 타이중 1곳(현금 %d칸 · 포인트 %d칸 / 1×365=365칸) 365일 세전 현금·아워드 포인트 '
        '실측(2026-11-24 · 6번(@jin_6) 전달본), 누적 28곳 원본 가운데 기존 정본에 없는 코드 1개만 골라 '
        '추가(기존 27곳 중복 0건), 현금 %s~%s원 · 결번 20일(2026-12-12 · 2026-12-31 · 2027-11-13~11-30), '
        '포인트 %s~%sP · 결번 21일(2026-12-05 · 2026-12-12 · 2026-12-31 · 2027-11-13~11-30 — 19,000P 최저는 '
        '2026-12-01 하루), 현금·포인트가 함께 2027-11-12 에 끊겨 11-13~30 18일이 예약 창 끝, '
        '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳'
        % (cash, pts,
           format(min(v for v in card['rates'].values() if isinstance(v, (int, float))), ','),
           format(max(v for v in card['rates'].values() if isinstance(v, (int, float))), ','),
           format(min(v for v in card['points'].values() if isinstance(v, int)), ','),
           format(max(v for v in card['points'].values() if isinstance(v, int)), ',')))
    if '대만 8차 1곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + ' / ' + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 1곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for x in master['hotels'] if x.get('group') == 'marriott'), cash, pts))
    print('  %s %s %s' % (hid, card['code'], card['name']))
    print('  note: %s' % card['note'])


if __name__ == '__main__':
    main()
