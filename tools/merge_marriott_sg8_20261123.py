#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""③ 메리어트 — 싱가포르 8곳 병합 (92 → 100곳).

정본 `data/master_db.json` 에만 쓴다(배포본은 이어서 `master_db.py inject`).

입력(모두 2026-11-22~23 No.2 365일 실측 · marriott.com availabilityCalendar):
  · downloads/marriott_measured_no2_batch1.json — m41 SINJW · m42 SINWH
  · downloads/marriott_measured_no2_sg20.json    — m43 SINDW · m44 SINTC · m45 SINLB
                                                   · m46 SINSL · m47 SINRZ · m48 SINDT

규칙:
  · 기존 92곳(중국 40 · 한국 40 · 일본 12)은 값·순서 그대로 두고 뒤에 8곳을 붙인다.
  · 현금(세전 KRW)·아워드 포인트의 null 은 보간하지 않고 그대로 둔다.
  · SINRZ(리츠칼튼 밀레니아)는 포인트 캘린더가 365일 전부 null — note 에 「아워드 포인트 미게시」.
  · ① 호텔럭스(tab1_vip.json)와 겹치는 8곳은 양쪽에 alsoIn 을 걸고, index.html 의
    MAR_CROSS·LUX_REF_MAR 은 별도로 손본다(이 스크립트는 데이터만 다룬다).
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import master_db as M  # noqa: E402

FILES = [('downloads/marriott_measured_no2_batch1.json', 'marriott_measured_no2_batch1', '2026-11-22'),
         ('downloads/marriott_measured_no2_sg20.json', 'marriott_measured_no2_sg20', '2026-11-23')]
WANT = ['m41', 'm42', 'm43', 'm44', 'm45', 'm46', 'm47', 'm48']
# ① 호텔럭스 짝 — 2026-11-23 tab1_vip.json 전수 대조(코드·영문명·국문명)에서 확인한 ID
LUX = {'m41': 'h75', 'm42': 'h76', 'm43': 'h78', 'm44': 'h74',
       'm45': 'h109', 'm46': 'h77', 'm47': 'h82', 'm48': 'h93'}


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
    notes.append('null 은 그 날 값 미게시이며 보간하지 않았습니다.')

    if h['id'] == 'm47':
        promo = '아워드 포인트 캘린더 미게시(0일) · 현금 343일'
    else:
        promo = '아워드 포인트 캘린더(%s 기준) · 포인트 %d일 확보' % (day, pt_days)

    return {
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
        'alsoIn': LUX[h['id']],
        'alsoInLabel': '① 호텔럭스',
    }


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

    # 메리어트 묶음 맨 뒤(일본 j12 다음)에 붙인다 — 기존 순서 보존
    pos = max(i for i, h in enumerate(master['hotels']) if h.get('group') == 'marriott') + 1
    master['hotels'][pos:pos] = new

    # ① 호텔럭스 쪽에도 alsoIn (짝이 비어 있을 때만)
    by_id = {h['id']: h for h in master['hotels']}
    for i in WANT:
        lux = by_id[LUX[i]]
        if lux.get('group') != 'lux':
            raise SystemExit('%s 가 lux 탭이 아닙니다' % LUX[i])
        print('  alsoIn %s(%s) ↔ %s(%s)' % (i, rows[i]['english'][:44],
                                            LUX[i], lux.get('english') or lux.get('name')))
        if lux.get('alsoIn') and lux['alsoIn'] != i:
            raise SystemExit('%s 에 이미 다른 alsoIn: %r' % (LUX[i], lux['alsoIn']))
        lux['alsoIn'] = i

    for rel, label, _day in FILES:
        src = os.path.basename(rel)
        if src not in master['sources']:
            master['sources'].append(src)

    line = (' / 2026-11-23 KST ③ 메리어트 싱가포르 8곳 병합(92→100곳 · 동남아 8) — '
            'JW 메리어트 싱가포르 사우스비치(SINJW) · W 센토사 코브(SINWH) · 디자인 호텔스 '
            '웨어하우스(SINDW)·21 카펜터(SINTC) · 럭셔리 컬렉션 프레이저스 하우스(SINLB)·라우루스(SINSL) · '
            '리츠칼튼 밀레니아(SINRZ) · 메리어트 탕 플라자(SINDT) 365일 현금(세전)·아워드 포인트 실측, '
            '리츠칼튼 밀레니아는 포인트 캘린더 미게시, 8곳 모두 ① 호텔럭스와 alsoIn 연결.')
    if '싱가포르 8곳 병합' not in master.get('extended', ''):
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
