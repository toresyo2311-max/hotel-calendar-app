#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 오세아니아 2차 잔여 10곳 + 대만 1차 4곳 병합 (270 → 284곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py refresh` → `inject`).

입력(2026-11-23~24 6번(@jin_6) 실측 · marriott.com availabilityCalendar):
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-23-1246/received/
      0-marriott-wave1-oceania-part2-24.json — 24곳 가운데 **뒤 10곳**(앞 14곳은 m198~m211 로 이미 수록)
  · memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0426/received/
      0-marriott-wave1-tw-hk-mo-47.json — 대만 1차 4곳(KHHGM·KHHLC·KHHMC·TPELF)
  365일(2026-12-01~2027-11-30) 세전 현금 최저가(rates, KRW) + 아워드 포인트(points).

규칙:
  · 오세아니아 10곳은 m271~m280(오세아니아 37→47), 대만 4곳은 m281~m284(대만 4)로
    메리어트 묶음 맨 뒤에 붙인다. 기존 270곳은 값·순서·alsoIn 그대로.
  · note 규칙은 오세아니아 1·2차와 같다 — 코드·국가/도시·현금/포인트 일수·값 범위·결번 구간·
    호주 세금 포함 표시·조회 한도·null 보간 없음.
  · 호주 10곳은 1·2차 호주 26곳과 같이 달력 표시값이 세금 포함 총액이다(원자료 source 문구는
    「세금·수수료 별도」로 1·2차와 같고, 1·2차도 같은 문구에 note 로 세금 포함을 적었다).
  · 브랜드 표기는 기존 카드와 맞춘다 — 원본 「포인트」는 「포 포인츠 바이 쉐라톤」.
  · 6번이 전한 특이사항은 값에서 확인되는 사실만 note 에 적는다(SYDCF 실제 명칭 · ADLMC 현금
    미판매 · CNSSI 격일 포인트 폐쇄 · PERRZ/PERWI/HBALC 고가일 · KHHLC 1천만 원대 실측값 ·
    KHHGM 2027-06-26~11-30 체크인 불가 · TPELF 포인트 단일가).
  · ① 호텔럭스(tab1_vip.json 161곳)와 코드·영문명·국문명·도시를 전수 대조한 결과 같은 호텔이
    한 곳도 없어 alsoIn 을 붙이지 않는다.
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

OC_SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-23-1246/received/'
          '0-marriott-wave1-oceania-part2-24.json')
TW_SRC = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-24-0426/received/'
          '0-marriott-wave1-tw-hk-mo-47.json')
DAY = '2026-11-24'
OC_FIRST = 271          # m271~m280
TW_FIRST = 281          # m281~m284
# 원자료 브랜드 표기 → 기존 카드와 같은 이름
BRAND_FIX = {'포인트': '포 포인츠 바이 쉐라톤'}
# 원자료 국문명을 기존 카드 표기(브랜드 국문 + 도시 + 영문 지명)로 바로잡는다(값은 원자료 그대로)
NAME_FIX = {
    'SYDCF': '포 포인츠 바이 쉐라톤 시드니 Central Park',
    'PERFP': '포 포인츠 바이 쉐라톤 퍼스',
    'TPELF': '포 포인츠 바이 쉐라톤 린커우',
}
# 호주 10곳 — 현지 가격표시 규정상 달력 표시값이 세금 포함 총액
AUS = {'SYDCF', 'ADLMC', 'CBRAK', 'PERRZ', 'PERAL', 'PERWI', 'PERMC', 'PERFP',
       'CNSSI', 'HBALC'}
# 호텔별 특이사항 — 6번이 전한 내용 가운데 값에서 그대로 확인되는 사실만 적는다
EXTRA = {
    'SYDCF': '2027-10-01~11-30 61일이 현금·포인트 함께 결번입니다(2027-09-30 이후 값 없음 — '
             '판매 중단인지 호텔별 예약창 상한인지는 구분하지 않음)',
    'ADLMC': '2027-09-30~10-17 18일은 현금만 결번이고 포인트는 게시됩니다 — 6번이 현금 미판매로 '
             '교차 확인했습니다(2027-04-08~10 3일도 현금 결번)',
    'PERRZ': '2027-10월 이벤트 기간이 창 안 최고 구간입니다(2027-10-02·10-10·10-17 2,408,589원)',
    'PERWI': '2026-12-10 4,143,951원이 창 안 최고가입니다 — 연말·이벤트 고가일이 많습니다',
    'HBALC': '2027-03-04~05 197만~204만원이 창 안 최고 구간입니다 — 연말·이벤트 고가일이 많습니다',
    'CNSSI': '2027-07~08월 아워드 포인트가 격일로 비어 있습니다 — 성수기 재고 폐쇄(6번 확인)',
    'KHHGM': '2027-06-26~11-30 158일은 현금·포인트가 함께 미판매입니다 — 6번이 1박·2박 모두 '
             '체크인 불가로 확인했고, 디자인 호텔스 포인트는 24,000~36,500P에 판매됩니다',
    'KHHLC': '2026-12-04 현금 13,964,706원은 1박 1천만 원 이상이지만 6번이 교차 확인한 실측값이라 '
             '그대로 실었습니다(다음 날 2026-12-05는 855,766원 — 시스템 이상값 표시 대상)',
    'TPELF': '포인트가 연중 26,000P 단일가입니다',
}
TW_TAX_NOTE = {'CNSSI': '포인트는 객실료에 세금을 더한 금액 기준으로 게시된 값입니다(6번 안내)',
               'HBALC': '포인트는 객실료에 세금을 더한 금액 기준으로 게시된 값입니다(6번 안내)'}


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


def load_oc():
    with open(OC_SRC, encoding='utf-8') as fp:
        doc = json.load(fp)
    if doc['checked_at'] != DAY:
        raise SystemExit('오세아니아 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = doc['hotels']
    if len(hotels) != 24:
        raise SystemExit('오세아니아 원본 호텔 %d곳 (24 이어야 함)' % len(hotels))
    tail = hotels[14:]
    if len(tail) != 10:
        raise SystemExit('오세아니아 뒤 10곳이 아님: %d' % len(tail))
    for h in tail:
        if h['country'] != '호주':
            raise SystemExit('%s 국가 %s (호주 이어야 함)' % (h['code'], h['country']))
    return tail


def load_tw():
    with open(TW_SRC, encoding='utf-8') as fp:
        doc = json.load(fp)
    if doc['checked_at'] != DAY:
        raise SystemExit('대만 원본 checked_at %s (기대 %s)' % (doc['checked_at'], DAY))
    hotels = doc['hotels']
    if len(hotels) != 4:
        raise SystemExit('대만 원본 호텔 %d곳 (4 이어야 함)' % len(hotels))
    for h in hotels:
        if h['country'] != '대만':
            raise SystemExit('%s 국가 %s (대만 이어야 함)' % (h['code'], h['country']))
    return hotels


def build(h, hid, region, label):
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
    if not cash_vals:
        raise SystemExit('%s 현금 값 0칸 — 수록 기준 확인 필요' % h['code'])

    notes = ['%s · %s %s · 현금 %d일/365 · 아워드 포인트 %d일/365' % (
        h['code'], h['country'], h['city'], cash_days, pt_days)]
    tax = ' (세금 포함 총액)' if h['code'] in AUS else ' (세전)'
    notes.append('현금%s %s~%s원' % (tax, format(min(cash_vals), ','), format(max(cash_vals), ',')))
    if pt_vals:
        notes.append('포인트 %s~%sP' % (format(min(pt_vals), ','), format(max(pt_vals), ',')))
    else:
        notes.append('아워드 포인트 미게시 — 포인트 캘린더 0일(365일 전부 null)')

    cash_gap = ranges([d for d, v in rates.items() if not isinstance(v, (int, float))])
    pt_gap = ranges([d for d, v in pt_map.items() if not isinstance(v, int)])
    if cash_gap:
        notes.append('현금 결번 %d개 구간(%s)' % (len(cash_gap), ' · '.join(cash_gap)))
    if pt_gap and pt_vals:
        notes.append('포인트 결번 %d개 구간(%s)' % (len(pt_gap), ' · '.join(pt_gap)))
    if h['code'] in EXTRA:
        notes.append(EXTRA[h['code']])
    if h['code'] in TW_TAX_NOTE:
        notes.append(TW_TAX_NOTE[h['code']])
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
        'region': region,
        'name': NAME_FIX.get(h['code'], h['name']),
        'english': h['english'],
        'promotion': promo,
        'source': ('메리어트 공홈 요금 캘린더(세금·수수료 별도 KRW) · %s 조회 / '
                   '아워드 포인트 캘린더(%s 기준) · 6번 실측 %s 365일' % (DAY, DAY, label)),
        'code': h['code'],
        'rates': rates,
        'points': pt_map,
        'note': ' · '.join(notes),
    }


def main():
    with open(M.MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    oc = load_oc()
    tw = load_tw()

    ids = {h['id'] for h in master['hotels']}
    codes = {h.get('code') for h in master['hotels'] if h.get('code')}
    names = {(h.get('english') or '').strip().lower() for h in master['hotels']}
    new = []
    for i, h in enumerate(oc):
        hid = 'm%d' % (OC_FIRST + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s' % h['code'])
        if h['english'].strip().lower() in names:
            raise SystemExit('이미 있는 영문명: %s' % h['english'])
        new.append(build(h, hid, '오세아니아', 'marriott-wave1-oceania-part2 잔여 10곳'))
    for i, h in enumerate(tw):
        hid = 'm%d' % (TW_FIRST + i)
        if hid in ids:
            raise SystemExit('이미 있는 id: %s' % hid)
        if h['code'] in codes:
            raise SystemExit('이미 있는 code: %s' % h['code'])
        if h['english'].strip().lower() in names:
            raise SystemExit('이미 있는 영문명: %s' % h['english'])
        new.append(build(h, hid, '대만', 'marriott-wave1-tw-hk-mo 대만 1차 4곳'))

    # 메리어트 묶음 맨 뒤에 붙인다 — 기존 270곳 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    tw_name = os.path.basename(TW_SRC)
    if tw_name not in master['sources']:
        master['sources'].append(tw_name)

    cash = sum(1 for h in new for v in h['rates'].values() if isinstance(v, (int, float)))
    pts = sum(1 for h in new for v in h['points'].values() if isinstance(v, int))
    oc_cash = sum(1 for h in new[:10] for v in h['rates'].values() if isinstance(v, (int, float)))
    oc_pts = sum(1 for h in new[:10] for v in h['points'].values() if isinstance(v, int))
    tw_cash = sum(1 for h in new[10:] for v in h['rates'].values() if isinstance(v, (int, float)))
    tw_pts = sum(1 for h in new[10:] for v in h['points'].values() if isinstance(v, int))
    line = (' / %s KST ③ 메리어트 오세아니아 2차 잔여 10곳 · 대만 1차 4곳 병합(270→284곳 · '
            '오세아니아 47 · 대만 4) — SYDCF 포 포인츠 시드니 Central Park ~ HBALC 럭셔리 컬렉션 '
            '호바트 Tasman 10곳(현금 %d칸 · 포인트 %d칸 / 10×365=3,650칸) + KHHGM 디자인 호텔스 '
            '가오슝 Gloria Manor · KHHLC 럭셔리 컬렉션 가오슝 AMNIS · KHHMC 메리어트 가오슝 · '
            'TPELF 포 포인츠 린커우 4곳(현금 %d칸 · 포인트 %d칸 / 4×365=1,460칸) 365일 세전 '
            '현금·아워드 포인트 실측(2026-11-23~24 · 6번(@jin_6) 전달본), 호주 10곳은 1·2차 호주 '
            '26곳과 같이 현지 규정상 세금 포함 총액, KHHLC 2026-12-04 13,964,706원은 6번 교차 '
            '확인 실측값, KHHGM 2027-06-26~11-30 158일 미판매, ADLMC 2027-09-30~10-17 현금만 '
            '결번, CNSSI 2027-07~08월 포인트 격일 폐쇄, ① 호텔럭스 161곳과 전수 대조 — 겹침 0곳'
            % (DAY, oc_cash, oc_pts, tw_cash, tw_pts))
    if '오세아니아 2차 잔여 10곳 · 대만 1차 4곳 병합' not in master.get('extended', ''):
        master['extended'] = master.get('extended', '') + line

    tmp = M.MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, M.MASTER)
    print('병합 완료 — 호텔 %d곳 (메리어트 %d곳 · 신규 14곳 현금 %d칸 · 포인트 %d칸)' % (
        len(master['hotels']),
        sum(1 for h in master['hotels'] if h.get('group') == 'marriott'), cash, pts))
    for hid in ('m271', 'm280', 'm281', 'm284'):
        h = next((x for x in master['hotels'] if x['id'] == hid), None)
        if h:
            print('  %s %s %s (현금 %d칸 · 포인트 %d칸)' % (
                hid, h['code'], h['name'],
                sum(1 for v in h['rates'].values() if isinstance(v, (int, float))),
                sum(1 for v in h['points'].values() if isinstance(v, int))))


if __name__ == '__main__':
    main()
