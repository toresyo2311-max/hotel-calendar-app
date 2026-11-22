#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 오세아니아 1차 23곳 병합 (114 → 137곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-22 No.6 실측 · marriott.com availabilityCalendar):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-23-0252/received/
      0-marriott-wave1-oceania-part1-25.json — 25곳 × 365일(2026-12-01~2027-11-30)
    세전 현금 최저가(rates, KRW) + 아워드 포인트(points)

규칙:
  · 25곳 가운데 NANWI(웨스틴 피지 골프 — 호텔 페이지 404, 전 기간 null)와
    NANTI(쉐라톤 나디 토코리키 — 1박·3박 모두 전 기간 체크인 불가, 판매 중단) 2곳은
    한국 SELAK(영업 종료)과 같은 기준으로 뺀다. 남은 23곳을 114곳 뒤에 붙인다.
  · 기존 114곳(중국 40 · 한국 40 · 일본 12 · 싱가포르 22)은 값·순서 그대로 둔다.
  · null 은 보간하지 않는다(2027-11-07~12 체크인 불가 · 2027-11-13 이후 조회 한도).
  · 브랜드 표기는 기존 카드와 맞춘다 — 원본 「포인트」는 「포 포인츠 바이 쉐라톤」.
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명을 전수 대조한 결과
    겹치는 호텔이 없어 alsoIn 연결이 없다.
  · 호주 12곳은 현지 가격표시 규정상 달력 표시값이 세금 포함 총액이고,
    BOBWI(웨스틴 보라보라)는 목적지 피가 포함된 표시값 그대로임을 note 에 적는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-23-0252/received/'
       '0-marriott-wave1-oceania-part1-25.json')
DAY = '2026-11-22'
EXCLUDE = {'NANWI': '웨스틴 피지 골프 — 호텔 페이지 404(미취급), 전 기간 null',
           'NANTI': '쉐라톤 나디 토코리키 — 1박·3박 모두 전 기간 체크인 불가(판매 중단)'}
# 원본 브랜드 표기 → 기존 카드와 같은 이름
BRAND_FIX = {'포인트': '포 포인츠 바이 쉐라톤'}
NAME_FIX = {'AKLFP': '포 포인츠 바이 쉐라톤 오클랜드'}
# 호주 — 현지 가격표시 규정상 달력 표시값이 세금 포함 총액
AUS = {'OOLAC', 'OOLSP', 'OOLGS', 'DRWCY', 'MELAC', 'MELWH', 'MELAH',
       'MELMD', 'MELRZ', 'MELDL', 'MELMC', 'MELSI'}
# 호텔별 특이사항(No.6 교차검증 전달분 · 원본 JSON 에는 note 가 없다)
EXTRA = {
    'NANSI': '2026-12 일부 31일만 현금 판매 후 2027-01-03부터 판매 중단(1박·3박 재확인)',
    'OOLAC': '2026-12-18 개관 — 개관 전 2026-12-01~12-17은 현금 미판매',
    'POMSI': '2027-07-11 이후 현금·포인트가 함께 미게시(143일) — 판매 중단인지 예약창 밖인지는 구분하지 않음',
    'BOBXR': '포인트는 178일만 게시 — 성수기·최소숙박일에는 아워드 포인트 재고가 없음',
    'BOBWI': '목적지 피(destination fee)가 포함된 달력 표시값 그대로 수록',
    'MELRZ': '2027-09-30~10-24 현금·포인트가 함께 빈 25일',
    'GUMWI': '2026-12-26~27·12-30~2027-01-01은 연말 최소숙박일이라 포인트 재고가 없음',
}
NO_POINT = {'NANSI', 'OOLAC', 'POMEA'}


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
        raise SystemExit('원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = [h for h in doc['hotels'] if h['code'] not in EXCLUDE]
    dropped = [h['code'] for h in doc['hotels'] if h['code'] in EXCLUDE]
    if sorted(dropped) != sorted(EXCLUDE):
        raise SystemExit('제외 대상이 원본과 다름: %s' % dropped)
    if len(hotels) != 23:
        raise SystemExit('유효 호텔 %d곳 (23 이어야 함)' % len(hotels))
    return hotels, os.path.basename(SRC)


def build(h, hid):
    rates, points = h['rates'], h['points']
    for name, vals in (('rates', rates), ('points', points)):
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['code'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['code'], name, d))
    cash_days = sum(1 for v in rates.values() if isinstance(v, (int, float)))
    pt_days = sum(1 for v in points.values() if isinstance(v, int))
    cash_vals = [v for v in rates.values() if isinstance(v, (int, float))]
    pt_vals = [v for v in points.values() if isinstance(v, int)]
    if not cash_vals:
        raise SystemExit('%s 현금 값 0칸 — 제외 기준 확인 필요' % h['code'])

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    tax = ' (세금 포함 총액)' if h['code'] in AUS else ' (세전)'
    notes.append('현금%s %s~%s원' % (tax, format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트 미게시 — 포인트 캘린더 0일(365일 전부 null)')

    cash_gap = ranges([d for d, v in rates.items() if not isinstance(v, (int, float))])
    pt_gap = ranges([d for d, v in points.items() if not isinstance(v, int)])
    if cash_gap:
        notes.append('현금 결번 %d개 구간(%s)' % (len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
        notes.append('포인트 결번 %d개 구간(%s)' % (len(pt_gap), ' · '.join(pt_gap)))
    if h['code'] in EXTRA:
        notes.append(EXTRA[h['code']])
    if h['code'] in AUS:
        notes.append('호주는 현지 가격표시 규정상 달력 표시값이 세금 포함 총액과 같습니다')
    notes.append('2027-11-07~12는 체크인 불가, 2027-11-13 이후는 조회 한도(오늘+355일)이며 '
                 '판매 중단과 구분하지 않습니다')
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    if pt_days:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (DAY, pt_days)
    else:
        promo = '아워드 포인트 캘린더 미게시(0일) · 현금 %d일' % cash_days

    return {
        'id': hid,
        'group': 'marriott',
        'brand': BRAND_FIX.get(h['brand'], h['brand']),
        'city': h['city'],
        'name': NAME_FIX.get(h['code'], h['name']),
        'english': h['english'],
        'region': '오세아니아',
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · No.6 실측 marriott-wave1-oceania-part1 365일'
                   % (DAY, DAY)),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': ' · '.join(notes),
    }


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    src, srcname = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('group') == 'marriott'}
    new = []
    for i, h in enumerate(src):
        hid = 'm%02d' % (63 + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s' % h['code'])
        new.append(build(h, hid))

    # 메리어트 묶음 맨 뒤(싱가포르 22곳 다음)에 붙인다 — 기존 114곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    if srcname not in master['sources']:
        master['sources'].append(srcname)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    line = (' / 2026-11-23 KST ③ 메리어트 오세아니아 1차 23곳 병합(114→137곳 · 오세아니아 23) — '
            'GUMWI 웨스틴 괌 ~ MELSI 쉐라톤 멜버른 23곳 365일 세전 현금·아워드 포인트 실측'
            '(현금 %d칸 · 포인트 %d칸 / 23×365=8,395칸), 404 미취급 NANWI(웨스틴 피지 골프)와 '
            '판매 중단 NANTI(쉐라톤 나디 토코리키)는 SELAK 과 같은 기준으로 제외, '
            'NANSI·OOLAC·POMEA 는 포인트 0일, 호주 12곳은 현지 규정상 세금 포함 총액, '
            '① 호텔럭스 161곳과 겹침 0곳(alsoIn 없음)' % (cash, pts))
    if '오세아니아 1차 23곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 23곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))


if __name__ == '__main__':
    main()
