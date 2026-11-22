#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 싱가포르 중반 7곳 병합 (100 → 107곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(2026-11-23 No.2 365일 실측 · marriott.com availabilityCalendar):
  · downloads/marriott_measured_no2_sg_mid7.json — m49 SINXR · m50 SINSI · m51 SINNV
    · m52 SINEB · m53 SINAD · m54 SINAM · m55 SINHS
  · 상태 기록 downloads/marriott_no2_sg_mid7_status.md — 호텔별 결번 사유·교차검증

규칙:
  · 기존 100곳(중국 40 · 한국 40 · 일본 12 · 싱가포르 8)은 값·순서 그대로 두고 뒤에 7곳을 붙인다.
  · 현금(세전 KRW)·아워드 포인트의 null 은 보간하지 않고 그대로 둔다.
  · SINHS(Stripes Chinatown)는 아워드 포인트가 365일 전부 미게시 — 0일로 두고 note 에
    「4회 독립 표본 조회에서도 재고 미게시」라는 사실을 정직하게 적는다.
  · ① 호텔럭스(tab1_vip.json)와 코드·영문명·국문명을 전수 대조한 결과 겹치는 4곳만
    alsoIn 으로 잇는다(나머지 3곳은 ① 탭에 없어 공홈 단일 링크).
    index.html 의 MAR_CROSS·LUX_REF_MAR 은 별도로 손본다(이 스크립트는 데이터만 다룬다).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

FILES = [('downloads/marriott_measured_no2_sg_mid7.json',
          'marriott_measured_no2_sg_mid7', '2026-11-23')]
WANT = ['m49', 'm50', 'm51', 'm52', 'm53', 'm54', 'm55']
# ① 호텔럭스 짝 — 2026-11-23 tab1_vip.json 전수 대조(코드·영문명·국문명)에서 확인한 ID
LUX = {'m49': 'h90',   # 세인트 레지스 싱가포르 (The St. Regis Singapore)
       'm52': 'h94',   # 싱가포르 에디션 (The Singapore Edition)
       'm53': 'h79',   # 덕스턴 리저브 싱가포르, 오토그래프 컬렉션
       'm54': 'h86'}   # 맥스웰 리저브 싱가포르, 오토그래프 컬렉션
# ① 탭에 없는 3곳 — 쉐라톤 타워스 · 알로프트 노베나 · 호텔 스트라이프스 차이나타운
NO_LUX = ['m50', 'm51', 'm55']
# 상태 기록(downloads/marriott_no2_sg_mid7_status.md)에서 옮긴 호텔별 결번 사유
EXTRA = {
    'm49': '현금 예약창 2027-11-12까지 · 2027-03-02는 포인트만 공백(현금은 판매)',
    'm50': '2026-12-01~02는 현금·포인트 모두 판매 중단 표시(Not available for check-in)',
    'm51': '2027-02-08은 포인트만 공백(현금은 판매)',
    'm52': '포인트 게시가 2027-11-12까지 — 이번 7곳 가운데 가장 길다(현금과 같은 날짜)',
    'm53': '2026-12-30~31은 포인트만 공백(현금은 판매)',
    'm54': '2027-10-07~11은 현금·포인트가 동시에 빈 5일(판매 중단)',
    'm55': ('아워드 포인트는 365일 전부 미게시 — 2026-12(1박) · 2027-01(1박) · 2027-03(1박) · '
            '2026-12(2박) 네 번의 독립 표본 조회에서 모두 "Not available for check-in"(HTTP 200)이었고 '
            '같은 기간 현금은 전일 판매였으므로, 매진이 아니라 아워드 재고 미게시로 판단해 0일로 두었습니다'),
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

    if h['id'] == 'm55':
        promo = '아워드 포인트 캘린더 미게시(0일) · 현금 %d일' % cash_days
    else:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (day, pt_days)

    row = {
        'id': h['id'],
        'group': 'marriott',
        'brand': h['brand'],
        'city': '싱가포르',
        'name': h['name'],
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

    # 메리어트 묶음 맨 뒤(싱가포르 8곳 다음)에 붙인다 — 기존 순서 보존
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
        lux['alsoIn'] = i   # ① 탭 자료 스키마에는 alsoInLabel 칸이 없다(기존 8쌍과 같은 방식)

    for rel, label, _day in FILES:
        src = os.path.basename(rel)
        if src not in master['sources']:
            master['sources'].append(src)

    line = (' / 2026-11-23 KST ③ 메리어트 싱가포르 중반 7곳 병합(100→107곳 · 동남아 15) — '
            '세인트레지스 싱가포르(SINXR) · 쉐라톤 타워스 싱가포르(SINSI) · 알로프트 노베나(SINNV) · '
            '에디션 싱가포르(SINEB) · 덕스턴 리저브(SINAD) · 맥스웰 리저브(SINAM) · '
            '스트라이프스 차이나타운(SINHS) 365일 현금(세전)·아워드 포인트 실측, '
            '스트라이프스 차이나타운은 4회 독립 조회에서도 아워드 재고 미게시(포인트 0일), '
            '① 호텔럭스와 겹치는 4곳(세인트레지스·에디션·덕스턴·맥스웰)은 alsoIn 연결.')
    if '싱가포르 중반 7곳 병합' not in master.get('extended', ''):
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
