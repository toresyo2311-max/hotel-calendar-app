#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 일본 2차 30곳 병합 (167 → 197곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-23 5번(@jin_5) 실측 · marriott.com availabilityCalendar):
  · memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0751/received/
      0-2026-11-23-marriott-jp-batch2-31-60.json — 30곳 × 365일(2026-12-01~2027-11-30)
      세전 현금 최저가(rates, KRW) + 아워드 포인트(points) + 호텔별 특이사항(note) + 교차검증 기록

규칙:
  · 일본 미수록 119곳 가운데 2차 묶음 31~60번(도쿄 15 · 나고야 7 · 나라 2 · 니세코 2 ·
    마쓰모토 2 · 닛코 1 · 루쓰쓰 1)을 메리어트 묶음 맨 뒤에 붙인다. 기존 167곳은 값·순서·alsoIn 그대로.
  · id 는 197곳 기준 순번인 m168~m197(No.2 지시).
  · 5번이 붙인 호텔별 note(교차검증 결과 · 결번 구간 · 시즌 고정가 · 고가일 근거)를 그대로 싣고
    앞에 코드만 붙인다 — 값의 성격을 잃지 않기 위해서다.
  · null 은 보간하지 않는다(2027-11-07~12 체크인 불가 · 2027-11-13 이후 조회 오픈 한도 등).
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한 결과 4곳이 같은 호텔이다
    (TYOJW↔h41 JW 메리어트 도쿄 · TYOAK↔h46 프린스 사쿠라 타워 · TYOAM↔h53 메즘 · TYOWI↔h60 웨스틴 도쿄).
    alsoIn 을 양방향으로 잇는다(index.html 의 MAR_CROSS 표에도 넣는다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-23-0751/received/'
       '0-2026-11-23-marriott-jp-batch2-31-60.json')
DAY = '2026-11-23'
FIRST_ID = 168
# ① 호텔럭스(161곳)와 같은 호텔 — 코드 → (럭스 id, 럭스 ref_id)
OVERLAP = {
    'TYOJW': ('h41', '68c361825597054d09e549db'),   # JW 메리어트 호텔 도쿄
    'TYOAK': ('h46', '5b48de93a4144f1a4f372576'),   # 더 프린스 사쿠라 타워 도쿄, 오토그래프 컬렉션
    'TYOAM': ('h53', '5e5e9c0da4a3e77950f3f6a8'),   # 메즘 도쿄, 오토그래프 컬렉션
    'TYOWI': ('h60', '5b35e54c74b5e5b4a112b336'),   # 웨스틴 도쿄
}
# 원자료의 국문명·브랜드가 잘린 호텔 — 영문명에 맞춰 바로잡는다(값은 원자료 그대로)
FIX = {
    'NGOFP': ('포 포인츠 바이 쉐라톤', '포 포인츠 바이 쉐라톤 나고야 Chubu International Airport'),
}
EXTRA_NOTE = {
    'NGOFP': '5번 원자료의 국문명·브랜드가 「포인트」로 잘려 있어 영문명(Four Points by Sheraton '
             'Nagoya, Chubu International Airport)에 맞춰 바로잡았습니다(요금·포인트 값은 원자료 그대로).',
    'MMJFJ': '소재지는 야마나시현 후지카와구치코(호텔명 그대로 Lake Yamanaka) — 5번이 마쓰모토 권역으로 '
             '묶어 조회한 표기를 그대로 두었습니다.',
}
SOURCE = ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
          '아워드 포인트 캘린더(%s 기준) · 5번 실측 marriott-jp-batch2-31-60 365일')


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
    idx = [h['idx'] for h in hotels]
    if idx != list(range(31, 61)):
        raise SystemExit('원본 idx 가 31~60 이 아님: %s' % idx)
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

    brand, kname = FIX.get(h['code'], (h['brand'], h['name']))
    notes = [h['note'].replace('**', '').replace('`', '').strip()]
    if h['code'] in EXTRA_NOTE:
        notes.append(EXTRA_NOTE[h['code']])
    notes.append('null 은 그 날 값 미게시(체크인 불가·예약 오픈 한도)이며 보간하지 않았습니다.')

    hid_ = {
        'id': hid,
        'group': 'marriott',
        'brand': brand,
        'city': h['city'],
        'region': '일본',
        'name': kname,
        'english': h['english'],
        'promotion': '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days),
        'source': SOURCE % (DAY, DAY),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': '%s · %s' % (h['code'], ' '.join(notes)),
    }
    if h['code'] in OVERLAP:
        hid_['alsoIn'] = OVERLAP[h['code']][0]
        hid_['alsoInLabel'] = '① 호텔럭스'
    return hid_


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

    # 메리어트 묶음 맨 뒤(일본 1차 30곳 다음)에 붙인다 — 기존 167곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    # ① 호텔럭스 쪽 alsoIn — 양방향 연결
    by_id = {h['id']: h for h in master['hotels']}
    for code, (lux_id, _ref) in OVERLAP.items():
        lux = by_id.get(lux_id)
        if not lux or lux.get('group') != 'lux':
            raise SystemExit('① 호텔럭스 %s 없음' % lux_id)
        if lux.get('alsoIn'):
            raise SystemExit('① 호텔럭스 %s 는 이미 alsoIn %s' % (lux_id, lux['alsoIn']))
        mar = next(x for x in new if x['code'] == code)
        lux['alsoIn'] = mar['id']

    if srcname not in master['sources']:
        master['sources'].append(srcname)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (' / 2026-11-23 KST ③ 메리어트 일본 2차 30곳 병합(167→197곳 · 일본 72) — '
            'NGOFG 페어필드 나고야 Gifu Seiryu Satoyama Park ~ MMJFJ 메리어트 마쓰모토 Fuji Lake '
            'Yamanaka 365일 세전 현금·아워드 포인트 실측(현금 %d칸 · 포인트 %d칸 / 30×365=10,950칸). '
            '도쿄 15 · 나고야 7 · 나라 2 · 니세코 2 · 마쓰모토 2 · 닛코 1 · 루쓰쓰 1. '
            'CTSRZ 리츠칼튼 니세코는 2027-01-01~03-31 90일 전면 결번(도시검색 Sold Out 3중 확인), '
            'TYOAR AC 호텔 도쿄 긴자는 2027-10-09~11-30 53일 판매중단, TYOCY 코트야드 도쿄 긴자·'
            'MMJFJ 메리어트 후지 레이크야마나카는 2027-10-01~11-30 61일 전면 결번, '
            'TYOJW 2026-12-31 20,166,007원은 연말 스위트 잔여 게시가(두 달력 뷰 일치). '
            '① 호텔럭스 161곳과 전수 대조 — 겹침 4곳(TYOJW↔h41 · TYOAK↔h46 · TYOAM↔h53 · '
            'TYOWI↔h60) alsoIn 양방향 연결' % (cash, pts))
    if '일본 2차 30곳 병합' not in master.get('extended', ''):
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
