#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 싱가포르 마지막 7곳 병합 (107 → 114곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-23 No.2 365일 실측 · marriott.com availabilityCalendar):
  · downloads/marriott_measured_no2_sg_last7.json — m56 SINWI · m57 SINCY · m58 SINTG
    · m59 SINTX · m60 SINVB · m61 SINFP · m62 SINSP
  · 상태 기록 downloads/marriott_no2_sg_last7_status.md — 호텔별 결번 사유·교차검증

규칙:
  · 기존 107곳(중국 40 · 한국 40 · 일본 12 · 싱가포르 15)은 값·순서 그대로 두고 뒤에 7곳을 붙인다.
  · 현금(세전 KRW)·아워드 포인트의 null 은 보간하지 않고 그대로 둔다.
  · 브랜드 이름은 기존 114곳과 같은 표기를 쓴다 — 원본의 「포인트」는 기존 카드와 같은
    「포 포인츠 바이 쉐라톤」으로 적는다(브랜드 구성 검사 EXPECT_BRANDS 와 같은 이름).
  · ① 호텔럭스(tab1_vip.json)와 코드·영문명·국문명을 전수 대조한 결과 겹치는 2곳만
    alsoIn 으로 잇는다(웨스틴 싱가포르 = h97 · 세랑군 하우스 리틀 인디아 = h89).
    나머지 5곳은 ① 탭에 같은 호텔이 없어 공홈 단일 링크다.
    index.html 의 MAR_CROSS·LUX_REF_MAR 은 별도로 손본다(이 스크립트는 데이터만 다룬다).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

FILES = [('downloads/marriott_measured_no2_sg_last7.json',
          'marriott_measured_no2_sg_last7', '2026-11-23')]
WANT = ['m56', 'm57', 'm58', 'm59', 'm60', 'm61', 'm62']
# ① 호텔럭스 짝 — 2026-11-23 tab1_vip.json(master_db lux 161곳) 전수 대조에서 확인한 ID
LUX = {'m56': 'h97',   # 웨스틴 싱가포르 (The Westin Singapore)
       'm58': 'h89'}   # 세랑군 하우스 리틀 인디아 싱가포르, 트리뷰트 포트폴리오 호텔
# ① 탭에 없는 5곳 — 코트야드 노베나 · Varel · Vagabond Club · 포인트 Riverview · 포인트 Jurong
NO_LUX = ['m57', 'm59', 'm60', 'm61', 'm62']
# 원본 브랜드 표기 → 기존 카드와 같은 이름
BRAND_FIX = {'포인트': '포 포인츠 바이 쉐라톤'}
# 호텔 이름 앞의 브랜드 표기도 기존 카드와 맞춘다(브랜드 칸과 카드 제목이 같은 이름이 되게)
NAME_FIX = {'m61': '포 포인츠 바이 쉐라톤 싱가포르 Riverview',
            'm62': '포 포인츠 바이 쉐라톤 싱가포르 Jurong'}
# 상태 기록(downloads/marriott_no2_sg_last7_status.md)에서 옮긴 호텔별 결번 사유
EXTRA = {
    'm56': '2026-12-31은 현금·포인트 모두 미판매(Not available for check-in) · '
           '2027-10-07~10이 최고가 1,684,578원(F1 싱가포르 GP 주간)',
    'm57': '2026-12-31은 현금·포인트 모두 미판매 · 10월 GP 주간 최고가 762,495원 뒤로 '
           '366,870/267,716원 두 밴드가 주 단위로 반복(공홈 검색 화면 값과 일치)',
    'm58': '2027-10-07~11은 현금·포인트가 동시에 빈 5일(판매 중단 · GP 주간) · '
           '2027-11-07~12도 미판매이고 그 뒤는 전역 조회 한도(오늘+355일)',
    'm59': '2026-04 개관 호텔 · 2026-12-31·2027-01-01은 현금 미판매(포인트는 12-31 판매) · '
           '10월 GP 주간 최고가 891,344원 · 첫 로드가 1회 404(invalidPath.mi)로 떠 재시도에서 정상 조회',
    'm60': '2027-10-07~11은 현금·포인트가 동시에 빈 5일(판매 중단) · '
           '2027-10-12~11-06이 402,827→571,723→585,531원 밴드로 길게 이어짐(검색 화면 값과 일치)',
    'm61': '포인트가 2·3·8·9·10월에 화~수요일 위주로 2~4일씩 비어 325일(현금은 343일) · '
           '2027-10-07~10은 현금 미판매(GP 주간)',
    'm62': '현금이 198,308/218,139원 두 밴드(주 단위) · 2027년 10월 GP 주간 317,293원 · '
           '2027-11-07~12 미판매 · 현금 원본은 세션 스로틀 때문에 12~2월(_c)·3~11월(_c2) 두 조각으로 '
           '받아 build 에서 병합했습니다',
}


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
    rows, meta = {}, {}
    for rel, label, day in FILES:
        path = os.path.join(os.path.dirname(os.path.dirname(M.ROOT)), rel)
        with open(path, encoding='utf-8') as fp:
            doc = json.load(fp)
        for h in doc['hotels']:
            if h['id'] in WANT:
                rows[h['id']] = h
                meta[h['id']] = (label, day, doc['measured_at'])
    missing = [i for i in WANT if i not in rows]
    if missing:
        raise SystemExit('실측 파일에 없는 호텔: %s' % missing)
    return rows, meta


def build(h, label, day):
    rates, points = h['rates'], h['points']
    for name, vals in (('rates', rates), ('points', points)):
        if len(vals) != 365:
            raise SystemExit('%s %s 칸 %d개 (365 이어야 함)' % (h['id'], name, len(vals)))
        for d in vals:
            if not (M.WINDOW_START <= d <= M.WINDOW_END):
                raise SystemExit('%s %s 날짜 %s 창 밖' % (h['id'], name, d))
    cash_days = sum(1 for v in rates.values() if v is not None)
    pt_days = sum(1 for v in points.values() if isinstance(v, int))
    cash_vals = [v for v in rates.values() if v is not None]
    pt_vals = [v for v in points.values() if isinstance(v, int)]

    notes = ['%s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (h['code'], cash_days, pt_days)]
    if cash_vals:
        notes.append('현금(세전) %s~%s원' % (format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트 미게시 — 포인트 캘린더 0일(365일 전부 null)')

    cash_gap = ranges([d for d, v in rates.items() if v is None])
    pt_gap = ranges([d for d, v in points.items() if v is None])
    if cash_gap:
        notes.append('현금 결번 %d개 구간(%s)' % (len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
        notes.append('포인트 결번 %d개 구간(%s)' % (len(pt_gap), ' · '.join(pt_gap)))
    notes.append(EXTRA[h['id']])
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    if not pt_vals:
        promo = '아워드 포인트 캘린더 미게시(0일) · 현금 %d일' % cash_days
    else:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (day, pt_days)

    row = {
        'id': h['id'],
        'group': 'marriott',
        'brand': BRAND_FIX.get(h['brand'], h['brand']),
        'city': '싱가포르',
        'name': NAME_FIX.get(h['id'], h['name']),
        'english': h['english'],
        'region': '동남아',
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · No.2 실측 %s 365일') % (day, day, label),
        'code': h['code'],
        'rates': rates,
        'points': points,
        'note': ' · '.join(notes),
    }
    if h['id'] in LUX:
        row['alsoIn'] = LUX[h['id']]
        row['alsoInLabel'] = '① 호텔럭스'
    return row


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    rows, meta = load()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('group') == 'marriott'}
    for i in WANT:
        if i in ids or rows[i]['code'] in codes:
            raise SystemExit('이미 있는 id/code: %s %s' % (i, rows[i]['code']))

    new = [build(rows[i], meta[i][0], meta[i][1]) for i in WANT]

    # 메리어트 묶음 맨 뒤(싱가포르 15곳 다음)에 붙인다 — 기존 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    # ① 호텔럭스 쪽에도 alsoIn (짝이 비어 있을 때만)
    by_id = {h['id']: h for h in master['hotels']}
    for i in WANT:
        if i not in LUX:
            print('  alsoIn 없음 — %s(%s) 는 ① 탭에 같은 호텔이 없음' % (i, rows[i]['english']))
            continue
        lux = by_id[LUX[i]]
        if lux.get('group') != 'lux':
            raise SystemExit('%s 가 lux 탭이 아닙니다' % LUX[i])
        print('  alsoIn %s(%s) ↔ %s(%s)' % (i, rows[i]['english'][:44],
                                            LUX[i], lux.get('english') or lux.get('name')))
        if lux.get('alsoIn') and lux['alsoIn'] != i:
            raise SystemExit('%s 에 이미 다른 alsoIn: %r' % (LUX[i], lux['alsoIn']))
        lux['alsoIn'] = i   # ① 탭 자료 스키마에는 alsoInLabel 칸이 없다(기존 12쌍과 같은 방식)

    for rel, label, _day in FILES:
        src = os.path.basename(rel)
        if src not in master['sources']:
            master['sources'].append(src)

    line = (' / 2026-11-23 KST ③ 메리어트 싱가포르 마지막 7곳 병합(107→114곳 · 동남아 22) — '
            '웨스틴 싱가포르(SINWI) · 코트야드 바이 메리어트 싱가포르 Novena(SINCY) · '
            '세랑군 하우스 리틀 인디아(SINTG) · Varel(SINTX) · 버갓본 클럽(SINVB) · '
            '포 포인츠 Riverview(SINFP) · 포 포인츠 Jurong(SINSP) 365일 현금(세전)·아워드 포인트 실측, '
            '① 호텔럭스와 겹치는 2곳(웨스틴 · 세랑군 하우스)은 alsoIn 연결 — 싱가포르 22곳 완결.')
    if '싱가포르 마지막 7곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳)' % (
        len(master['hotels']), sum(1 for h in master['hotels'] if h.get('group') == 'marriott')))


if __name__ == '__main__':
    main()
