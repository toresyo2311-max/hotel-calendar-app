#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 일본 3차 30곳 + 4차 29곳 병합 (211 → 270곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-23 5번(@jin_5) 실측 · marriott.com availabilityCalendar):
  · memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-1513/received/
      0-2026-11-23-marriott-jp-batch3-61-90.json  — 30곳 × 365일(2026-12-01~2027-11-30)
      0-2026-11-23-marriott-jp-batch4-91-119.json — 29곳 × 365일
      세전 현금 최저가(rates, KRW) + 아워드 포인트(points) + 호텔별 특이사항(note) + 교차검증 기록

규칙:
  · 일본 미수록 119곳 가운데 3차 61~90번(오사카 17 · 삿포로 6 · 마쓰모토 2 · 시즈오카 2 ·
    모리오카 1 · 센다이 1 · 야마구치 1)과 4차 91~119번(오사카 7 · 오키나와 5 · 요코하마 4 ·
    오카야마 3 · 이바라키 3 · 후쿠오카 2 · 히로시마 2 · 이키 1 · 하코네 1 · 하코다테 1)을
    메리어트 묶음 맨 뒤에 붙인다. 기존 211곳은 값·순서·alsoIn 그대로.
  · id 는 m212~m241(3차 30곳) · m242~m270(4차 29곳) — 오세아니아 2차(m198~m211) 다음 번호.
  · 5번이 붙인 호텔별 note(교차검증 결과 · 결번 구간 · 시즌 고정가 · 포인트 미개방 근거)를
    그대로 싣고 앞에 코드만 붙인다 — 값의 성격을 잃지 않기 위해서다.
  · null 은 보간하지 않는다(CTSKO 365일 판매중단 · OSAKO 포인트 365일 미게시 ·
    UBJSN 2027-04-01~11-30 미게시 · OKARN/OSACY/OSAMC/OKACR/TYOMH 2027-10월 이후 등).
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한 결과 같은 호텔이
    한 곳도 없어 alsoIn 을 붙이지 않는다(계산 근거는 아래 `--check` 출력 참고).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

BASE = '/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-1513/received/'
BATCHES = [
    # (파일, 첫 idx, 끝 idx, 첫 id 번호, 묶음 이름)
    ('0-2026-11-23-marriott-jp-batch3-61-90.json', 61, 90, 212, 'marriott-jp-batch3-61-90'),
    ('0-2026-11-23-marriott-jp-batch4-91-119.json', 91, 119, 242, 'marriott-jp-batch4-91-119'),
]
DAY = '2026-11-23'
# 현금 0칸이 정상인 호텔(전 기간 판매중단) — 값이 없다는 사실 자체가 실측 결과다.
CASH_ZERO_OK = {'CTSKO'}
# 아워드 포인트 캘린더가 전 기간 미게시인 호텔 — verify 의 「포인트 칸 없음」 검사에서 뺀다.
POINT_ZERO = {'OSAKO', 'TYOYY', 'TYOMH', 'HKDXF'}
SOURCE = ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
          '아워드 포인트 캘린더(%s 기준) · 5번 실측 %s 365일')


def load():
    out = []
    for fname, lo, hi, first, label in BATCHES:
        with open(BASE + fname, encoding='utf-8') as fp:
            doc = json.load(fp)
        if doc['checked_at'] != DAY:
            raise SystemExit('%s checked_at %s (기대 %s)' % (fname, doc['checked_at'], DAY))
        if doc.get('pending_measurement'):
            raise SystemExit('%s 미완료 항목이 남아 있음: %s' % (fname, doc['pending_measurement']))
        hotels = doc['hotels']
        if len(hotels) != hi - lo + 1:
            raise SystemExit('%s 호텔 %d곳 (기대 %d곳)' % (fname, len(hotels), hi - lo + 1))
        idx = [h['idx'] for h in hotels]
        if idx != list(range(lo, hi + 1)):
            raise SystemExit('%s idx 가 %d~%d 가 아님: %s' % (fname, lo, hi, idx))
        codes = [h['code'] for h in hotels]
        if len(set(codes)) != len(codes):
            raise SystemExit('%s 코드 중복: %s' % (fname, codes))
        out.append((hotels, first, label))
    return out


def build(h, hid, label):
    rates, points = h['rates'], h['points']
    for name in ('rates', 'points'):
        vals = h[name]
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['code'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['code'], name, d))
    cash_days = sum(1 for v in rates.values() if isinstance(v, (int, float)))
    pt_days = sum(1 for v in points.values() if isinstance(v, int))
    if not cash_days and h['code'] not in CASH_ZERO_OK:
        raise SystemExit('%s 현금 값 0칸 (허용 목록 밖)' % h['code'])
    if not pt_days and h['code'] not in POINT_ZERO:
        raise SystemExit('%s 포인트 값 0칸 (허용 목록 밖)' % h['code'])

    notes = [h['note'].replace('**', '').replace('`', '').strip()]
    notes.append('null 은 그 날 값 미게시(체크인 불가·예약 오픈 한도)이며 보간하지 않았습니다.')

    return {
        'id': hid,
        'group': 'marriott',
        'brand': h['brand'],
        'city': h['city'],
        'region': '일본',
        'name': h['name'],
        'english': h['english'],
        'promotion': '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days),
        'source': SOURCE % (DAY, DAY, label),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': '%s · %s' % (h['code'], ' '.join(notes)),
    }


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    batches = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('code')}
    new = []
    for hotels, first, label in batches:
        for i, h in enumerate(hotels):
            hid = 'm%d' % (first + i)
            if hid in ids:
                raise SystemExit('이미 있는 id: %s' % hid)
            if h['code'] in codes:
                raise SystemExit('이미 있는 code: %s' % h['code'])
            new.append(build(h, hid, label))

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 211곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    for _f, _lo, _hi, _first, label in BATCHES:
        name = '0-2026-11-23-%s.json' % label
        if name not in master['sources']:
            master['sources'].append(name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (' / 2026-11-23 KST ③ 메리어트 일본 3차 30곳 · 4차 29곳 병합(211→270곳 · 일본 131) — '
            'MMJCH 코트야드 마쓰모토 Hakuba ~ HIJFI 페어필드 히로시마 Sera 59곳 365일 세전 현금·'
            '아워드 포인트 실측(현금 %d칸 · 포인트 %d칸 / 59×365=21,535칸). 3차 30곳 — 오사카 17 · '
            '삿포로 6 · 마쓰모토 2 · 시즈오카 2 · 모리오카 1 · 센다이 1 · 야마구치 1, 4차 29곳 — '
            '오사카 7 · 오키나와 5 · 요코하마 4 · 오카야마 3 · 이바라키 3 · 후쿠오카 2 · 히로시마 2 · '
            '이키 1 · 하코네 1 · 하코다테 1. CTSKO 디자인 호텔스 삿포로는 현금 365일 전면 판매중단'
            '(포인트는 2027-10-26 하루 46,000P만 개방), OSAKO 디자인 호텔스 오쓰는 아워드 365일 '
            '미게시, UBJSN 디자인 호텔스 야마구치는 2027-04-01~11-30 244일 미게시, OSAMC 메리어트 '
            '오사카 Miyako·OKARN 르네상스 오키나와·OSACY 코트야드 오사카 신역은 2027-10월 이후 '
            '판매중단, OKACR 코트야드 오키나와는 2027-09-01~11-30 91일 미개방, TYOMH·TYOYY·HKDXF 는 '
            '아워드 미개방, TYOYY 코트야드 요코하마 신역은 2026-12-18 개관이다. '
            '① 호텔럭스 161곳과 코드·영문명·국문명·도시 전수 대조 — 겹침 0곳(alsoIn 없음)'
            % (cash, pts))
    if '일본 3차 30곳 · 4차 29곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 59곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))
    for hid in ('m212', 'm241', 'm242', 'm270'):
        h = next((x for x in master['hotels'] if x['id'] == hid), None)
        if h:
            print('  %s %s %s (현금 %d칸 · 포인트 %d칸)' % (
                hid, h['code'], h['name'],
                sum(1 for v in h['rates'].values() if isinstance(v, (int, float))),
                sum(1 for v in h['points'].values() if isinstance(v, int))))


if __name__ == '__main__':
    main()
