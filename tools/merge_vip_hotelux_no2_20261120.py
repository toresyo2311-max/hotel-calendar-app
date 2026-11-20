#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 탭 HoteLux 실측 병합 (2026-11-20, No.2 분담분 + 5·6번 전달분).

반영 내용
  · h08 그랜드 하얏트 후쿠오카 / h09 리츠칼튼 후쿠오카 / h10 콘래드 오사카 /
    h11 월도프 아스토리아 오사카 — 365일 전수 교체
      원본: downloads/hotelux_no2_2026-11-20.json (현지 통화 JPY 총액 × 앱 환율 8.3592)
  · h16 월도프 아스토리아 방콕 — 2026-12-01~2027-04-03 124일만 교체(5번 전달분, USD × 1,331.56),
    2027-04-04 이후 기존값 유지
  · h21 포시즌스 리조트 더 남하이 호이안 — 365일 전수 교체(6번 전달분, USD × 1,331.56)
  · h01 파라다이스 호텔 부산 — 요금은 그대로, `source` 에 예약 사이트 미입점 확인만 덧붙임

값은 고치기만 하고 counts·배포본은 건드리지 않는다 —
이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
NO2 = '/workspace/downloads/hotelux_no2_2026-11-20.json'
H16 = ('/workspace/memory/clones/f0ee2d96-jin_5/pickle/2026-11-20-0832/received/'
       '0-2026-11-20-vip-hotelux-h16-h20.json')
H21 = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-20-0909/received/'
       '0-hotelux-h21.json')
H22 = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-20-1018/received/'
       '0-hotelux-h22.json')
H67 = ('/workspace/memory/clones/06130525-jin489/pickle/2026-11-20-1057/received/'
       '0-2026-11-20_hotelux-shanghai-2hotels.json')
H23 = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-20-1150/received/'
       '0-hotelux-h23.json')
H1415 = ('/workspace/memory/clones/06130525-jin489/pickle/2026-11-20-1143/received/'
         '0-2026-11-20_hotelux-bangkok-2hotels.json')

USD_KRW = 1331.56
JPY_KRW = 8.3592

SRC_JP = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 상세 페이지가 '
          '호출하는 자체 요금 서비스로 2026-12-01~2027-11-30 365일 전수 조회(성인 2인·1실·1박, '
          '세금·수수료 포함 총액 "including tax & fees"). 예약 사이트는 KRW를 지원하지 않아 현지 통화(JPY) 총액을 '
          '앱 고정 환율 JPY 1 = ₩8.3592 로 환산(USD 1 = ₩1,331.56, 2026-11-19 기준). '
          '요금 없는 날(판매 마감·미오픈)은 빈칸으로 두었고 추정·보간하지 않았습니다.')
SRC_H16 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 5번(@jin_5) 전달분. '
           '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 USD 총액) '
           '2026-12-01~2027-04-03 124일. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
           '2027-04-04~11-30 은 2026-11-19 화면 가격 달력 조사값을 그대로 두었습니다.')
SRC_H21 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 6번(@jin_6) 전달분. '
           '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 USD 총액) '
           '2026-12-01~2027-11-30 365일 전수. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
           '요금 없는 날 68일(최소숙박 제한·판매 중지)은 빈칸이며 추정하지 않았습니다.')
SRC_H67 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 07:40~10:50 KST 4번(@jin_4) 전달분. '
           '예약 사이트 상세 페이지 조회(성인 2인·1실·1박, 세금·수수료 포함 화면 최저 객실가 · '
           '표시통화 USD) 2026-12-01~2027-11-30 365일 전수. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
           '요금 없는 날은 빈칸이며 추정하지 않았습니다.')
SRC_H23 = ('/workspace/memory/clones/146dd4d1-jin_6/pickle/2026-11-20-1150/received/'
       '0-hotelux-h23.json')
SRC_H1415 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 4번(@jin_4) 전달분. '
            '예약 사이트 상세 페이지 조회(성인 2인·1실·1박, 세금·수수료 포함 최저 요금제)로 '
            '%s일 실측. 실측하지 않은 날(미판매·미오픈)은 검색값을 남기지 않고 빈칸으로 두었습니다.')
SRC_H22 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 6번(@jin_6) 전달분. '
           '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 USD 총액) '
           '2026-12-01~2027-11-30 365일 전수. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
           '요금 없는 날 44일(2027-10-18~11-30 판매 개시 전)은 빈칸이며 추정하지 않았습니다.')
SRC_H01_ADD = (' · 예약 사이트 미입점 확인(2026-11-20, 예약 사이트 호텔 검색 "Busan" 결과 '
               '파크 하얏트 부산·시그니엘 부산·조선 부산 3곳뿐, "Paradise Hotel Busan" 0건) — '
               '기존 FHR·별도 조사 요금 유지')
EXT_ADD = (' / 2026-11-20 ① VIP 예약 사이트 실측 병합 — h08~h11 4곳 365일 전수(No.2, 예약 사이트 요금 '
           '서비스 1박 조회 · 세금 포함 총액 · JPY→₩) + h16 방콕 124일(5번) + h21 호이안 365일·h22 캄란베이 365일(6번) '
           'USD→₩ 교체, h01 파라다이스 부산 예약 사이트 미입점 확인')
SRC_FILES = ['VIP 예약 사이트 실측 2026-11-20 — h08~h11 4곳 365일 (No.2)',
             'VIP 예약 사이트 실측 2026-11-20 — h16 방콕 124일 (5번 전달)',
             'VIP 예약 사이트 실측 2026-11-20 — h21·h22·h23 365일 (6번 전달)',
             'VIP 예약 사이트 실측 2026-11-20 — h06·h07 상하이 365일 (4번 전달)',
             'VIP 예약 사이트 실측 2026-11-20 — h14·h15 방콕 실측일 (4번 전달)']


def load(path):
    with open(path, encoding='utf-8') as fp:
        return json.load(fp)


def main():
    master = load(MASTER)
    no2 = load(NO2)
    h16 = load(H16)['hotels']['h16']
    h21 = load(H21)
    h22 = load(H22)
    h67 = load(H67)
    h23 = load(H23)
    h1415 = load(H1415)
    byid = {h['id']: h for h in master['hotels']}

    # --- h08~h11: 365일 전수 교체
    for h in no2['hotels']:
        tgt = byid.get(h['id'])
        if not tgt:
            sys.exit('호텔 없음: %s' % h['id'])
        rates = {}
        for day in sorted(h['krw']):
            rates[day] = h['krw'][day]
        tgt['rates'] = rates
        vals = [(v, d) for d, v in rates.items() if v]
        low, lowday = min(vals)
        tgt['source'] = SRC_JP
        vip_days = sum(1 for d in h['detail'] if isinstance(h['detail'][d], dict)
                       and h['detail'][d].get('vip'))
        tgt['promotion'] = ('실측 최저 1박 %s원(%s) · 요금 있는 날 %d일 · '
                            'VIP(Thor·Prive) 요율 별도 표기 %d일'
                            % (f'{low:,}', lowday, len(vals), vip_days))

    # --- h16: 계측 124일만 교체
    tgt = byid['h16']
    rates = dict(tgt['rates'])
    n16 = 0
    for item in h16['daily']:
        day, usd = item['date'], item.get('usd')
        if usd is None:
            rates[day] = None          # 미실측 구간은 기존 Google 검색값을 남기지 않고 비운다
            continue
        rates[day] = int(round(usd * USD_KRW))
        n16 += 1
    tgt['rates'] = rates
    tgt['source'] = SRC_H16

    # --- h21: 365일 전수 교체
    tgt = byid['h21']
    rates = {}
    for day, usd in h21['rates'].items():
        rates[day] = int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None
    tgt['rates'] = rates
    tgt['source'] = SRC_H21

    # --- h22: 365일 전수 교체
    tgt = byid['h22']
    rates = {}
    for day, usd in h22['rates'].items():
        rates[day] = int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None
    tgt['rates'] = rates
    tgt['source'] = SRC_H22

    # --- h23 식스 센스 닌 반 베이: 365일 전수 교체
    tgt = byid['h23']
    rates = {}
    for day, usd in h23['rates'].items():
        rates[day] = int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None
    tgt['rates'] = rates
    tgt['source'] = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 6번(@jin_6) 전달분. '
                     '예약 사이트 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 USD 총액) '
                     '2026-12-01~2027-11-30 365일 전수. 앱 고정 환율 USD 1 = ₩1,331.56 로 환산. '
                     '요금 없는 날 73일은 빈칸이며 추정하지 않았습니다.')

    # --- h06 콘래드 상하이 · h07 세인트 레지스 징안: 365일 전수 교체
    for hid in ('h06', 'h07'):
        tgt = byid[hid]
        rates = {}
        for day, usd in (h67[hid].get('rates_usd') or {}).items():
            rates[day] = int(round(usd * USD_KRW)) if isinstance(usd, (int, float)) else None
        tgt['rates'] = rates
        tgt['source'] = SRC_H67

    # --- h14 페어몬트 방콕 수쿰윗 · h15 킴튼 말라이 방콕: 실측일만 채우고 나머지는 비운다
    for hid in ('h14', 'h15'):
        tgt = byid[hid]
        data = h1415[hid]
        import datetime as _dt
        rates = {}
        _d = _dt.date.fromisoformat('2026-12-01')
        while _d <= _dt.date.fromisoformat('2027-11-30'):
            rates[_d.isoformat()] = None
            _d += _dt.timedelta(days=1)
        n = 0
        for day, krw in (data.get('rates') or {}).items():
            if isinstance(krw, (int, float)):
                rates[day] = int(round(krw))
                n += 1
        tgt['rates'] = rates
        tgt['source'] = SRC_H1415 % n

    # --- h01: 본계정이 ① 탭에서 삭제 중이므로 다시 넣거나 고치지 않는다
    if 'h01' in byid:
        print('note: h01 이 아직 남아 있음 — 건드리지 않음(본계정 삭제 배포 대기)')

    # --- h04·h05·h12·h13: 90일(2026-12-01~2027-02-28)만 실측된 호텔의
    #     2027-03-01 이후에 남은 기존 검색값을 비운다(3번이 3~11월을 이미 HoteLux로 채웠으면 그대로 둔다).
    for hid in ('h04', 'h05', 'h12', 'h13'):
        h = byid.get(hid)
        if not h:
            continue
        src = h.get('source') or ''
        if '2027-02-28' in src and '실측' in src and 'HoteLux' in src:
            n = 0
            for day in list(h.get('rates') or {}):
                if day >= '2027-03-01' and h['rates'][day] is not None:
                    h['rates'][day] = None
                    n += 1
            print('null out %s after 2027-02-28: %d칸' % (hid, n))

    if EXT_ADD not in master['extended']:
        master['extended'] = master['extended'] + EXT_ADD
    for s in SRC_FILES:
        if s not in master['sources']:
            master['sources'].append(s)

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
    print('merged h08~h11 (365d each), h16 %dd, h21/h22/h06/h07 365d, h14/h15 실측일, h01 skip' % n16)


if __name__ == '__main__':
    main()
