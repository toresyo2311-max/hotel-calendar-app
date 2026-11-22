#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 일본 1차 30곳 병합 (137 → 167곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-23 5번(@jin_5) 실측 · marriott.com availabilityCalendar):
  · memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0421/received/
      0-2026-11-23-marriott-jp-batch1-30.json — 30곳 × 365일(2026-12-01~2027-11-30)
      세전 현금 최저가(rates, KRW) + 아워드 포인트(points) + 호텔별 특이사항(note) + 교차검증 기록

규칙:
  · 일본 미수록 119곳 가운데 1~30번(가고시마 2 · 가나자와 2 · 가루이자와 1 · 고베 5 · 교토 14 ·
    구마모토 1 · 나가사키 2 · 나고야 3)을 137곳 뒤에 붙인다. 기존 137곳은 값·순서 그대로 둔다.
  · 5번이 붙인 호텔별 note(교차검증 결과 · 결번 구간 · 시즌 고정가 · 고가일 근거)를 그대로 싣고
    앞에 코드만 붙인다 — 값의 성격을 잃지 않기 위해서다.
  · null 은 보간하지 않는다(2027-11-07~12 체크인 불가 · 2027-11-13 이후 조회 한도).
  · 소재지가 조회 권역과 다른 2곳(가나자와로 묶인 후쿠이 · 나가사키로 묶인 사가 우레시노)은
    5번의 권역 표기를 그대로 두고 note 에 실제 소재지를 적는다.
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명을 전수 대조한 결과 겹치는 호텔이 없어
    alsoIn·MAR_CROSS·LUX_REF_MAR 연결이 없다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0421/received/'
       '0-2026-11-23-marriott-jp-batch1-30.json')
DAY = '2026-11-23'
FIRST_ID = 86
# 소재지가 권역 표기와 다른 호텔 — 값은 그대로 두고 note 로 밝힌다
PLACE = {
    'KMQCY': '소재지는 후쿠이현 후쿠이시(가나자와에서 차로 약 1시간) — 5번이 가나자와 권역으로 묶어 조회.',
    'NGSSU': '소재지는 사가현 우레시노 온천(나가사키에서 차로 약 1시간) — 5번이 나가사키 권역으로 묶어 조회.',
}
SOURCE = ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
          '아워드 포인트 캘린더(%s 기준) · 5번 실측 marriott-jp-batch1-30 365일')


def load():
    with open(SRC, encoding='utf-8') as fp:
        doc = json.load(fp)
    if doc['checked_at'] != DAY:
        raise SystemExit('원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    if doc.get('pending_measurement'):
        raise SystemExit('미완료 항목이 남아 있음: %s' % doc['pending_measurement'])
    hotels = doc['hotels']
    if len(hotels) != 30:
        raise SystemExit('원본 호텔 %d곳 (30 이어야 함)' % len(hotels))
    codes = [h['code'] for h in hotels]
    if len(set(codes)) != len(codes):
        raise SystemExit('원본 코드 중복: %s' % codes)
    return hotels, os.path.basename(SRC)


def build(h, hid):
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
    if not cash_days:
        raise SystemExit('%s 현금 값 0칸' % h['code'])

    notes = [h['note'].replace('**', '').strip()]
    if h['code'] in PLACE:
        notes.append(PLACE[h['code']])
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
        'source': SOURCE % (DAY, DAY),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': '%s · %s' % (h['code'], ' '.join(notes)),
    }


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src, srcname = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('group') == 'marriott'}
    new = []
    for i, h in enumerate(src):
        hid = 'm%02d' % (FIRST_ID + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s' % h['code'])
        new.append(build(h, hid))

    # 메리어트 묶음 맨 뒤(오세아니아 23곳 다음)에 붙인다 — 기존 137곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    if srcname not in master['sources']:
        master['sources'].append(srcname)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (' / 2026-11-23 KST ③ 메리어트 일본 1차 30곳 병합(137→167곳 · 일본 42) — '
            'KOJSI 쉐라톤 가고시마 ~ NGOCY 코트야드 나고야 30곳 365일 세전 현금·아워드 포인트 '
            '실측(현금 %d칸 · 포인트 %d칸 / 30×365=10,950칸). 교토 14 · 고베 5 · 나고야 3 · '
            '가고시마 2 · 가나자와 2 · 나가사키 2 · 가루이자와 1 · 구마모토 1. UKBCY 코트야드 고베는 '
            '2027-07-04 이후 150일 결번(직접 로드·도시검색 Sold Out·다음 달 뷰 3중 확인), '
            'UKYAK 오토그래프 교토는 2027-10-01~11-30 61일 전면 결번, NGOAK·NGSMC 고가일은 '
            '도시검색 교차검증으로 실제 게시가 확인, 2027-11-13 이후는 조회 한도 null. '
            '① 호텔럭스 161곳과 겹침 0곳(alsoIn 없음)'
            % (cash, pts))
    if '일본 1차 30곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 30곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))


if __name__ == '__main__':
    main()
