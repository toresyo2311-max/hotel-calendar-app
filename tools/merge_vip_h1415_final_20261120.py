#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""① VIP 탭 h14·h15 방콕 최종 보완분 병합 (2026-11-20, 4번(@jin_4) 전달).

반영 내용
  · h14 페어몬트 방콕 수쿰윗 — 2026-12-01~2027-11-30 중 실측 322일(직전 301일 + 보완 21일,
    1차 실측 정정 3건 2027-04-08·09-28·10-03 포함). 판매 객실 0건 43일은 null.
  · h15 킴튼 말라이 방콕 — 실측 319일(직전 313일 + 보완 6일). 판매 객실 0건 46일은 null.
  · 두 호텔 모두 창 밖 값은 두지 않고, 요금 없는 날은 추정·보간 없이 null 로 둔다.
  · 환율: 4번이 현지 통화(THB) 세금 포함 총액을 THB 1 = 39.2177 로 환산해 100원 단위로
    반올림한 KRW 를 그대로 쓴다(직전 h14·h15 병합과 같은 방식). 앱 고정 환율은 계열 FX 표의
    THB 1 = ₩39.22 로, 39.2177 과 차이는 0.006%(100원 반올림 경계에서만 ±100원)이다.

값은 고치기만 하고 counts·배포본은 건드리지 않는다 —
이어서 `python3 tools/master_db.py refresh && python3 tools/master_db.py inject`.
"""
import json
import os
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = ('/workspace/memory/clones/06130525-jin489/pickle/2026-11-20-1221/received/'
       '0-2026-11-20_hotelux-bangkok-2hotels.json')

WINDOW_START = datetime.date(2026, 12, 1)
WINDOW_END = datetime.date(2027, 11, 30)

SRC_H14 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 4번(@jin_4) 전달분'
           '(1차 07:30~11:43 · 잔여 보완 11:50~12:15). '
           '예약 사이트 호텔 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 최저 요금제 — '
           '비환불 Advance Saver 포함)로 2026-12-01~2027-11-30 중 322일 실측. '
           '현지 통화(THB) 세금 포함 총액을 앱 고정 환율 THB 1 = ₩39.22 로 환산해 100원 단위로 적었습니다. '
           '판매 객실이 없던 43일(2027-10-18~11-30 중 11-15 제외)은 빈칸이며 추정하지 않았습니다. '
           '1차 실측에서 부분 로딩값이던 3일(2027-04-08 · 09-28 · 10-03)은 전수 응답으로 다시 재어 정정했고, '
           '2027-11-15는 재조회에서 판매 객실이 없어 1차 값 498,500원을 그대로 두었습니다.')
SRC_H15 = ('실측 요금 · [출처: 예약 사이트 직접 조회] 2026-11-20 KST 4번(@jin_4) 전달분'
           '(1차 07:30~11:43 · 잔여 보완 12:00~12:10). '
           '예약 사이트 호텔 상세 페이지 비로그인 조회(성인 2인·1실·1박, 세금·수수료 포함 최저 요금제 — '
           '조식·무료취소 포함 요금제가 최저인 구간 포함)로 2026-12-01~2027-11-30 중 319일 실측. '
           '현지 통화(THB) 세금 포함 총액을 앱 고정 환율 THB 1 = ₩39.22 로 환산해 100원 단위로 적었습니다. '
           '판매 객실이 없던 46일(2027-10-18~11-30 44일 + 2026-12-30·31 연말 매진)은 빈칸이며 추정하지 않았습니다.')
EXT_ADD = (' / 2026-11-20 12:2x KST ① VIP 예약 사이트 실측 보완 — h14 페어몬트 방콕 수쿰윗 322일'
           '(잔여 21일 추가 · 1차 정정 3건) · h15 킴튼 말라이 방콕 319일(잔여 6일 추가), 4번(@jin_4)')
SRC_FILE = 'VIP 예약 사이트 실측 2026-11-20 — h14·h15 방콕 보완 27일 + h14 정정 3건 (4번 전달)'


def window_days():
    d = WINDOW_START
    while d <= WINDOW_END:
        yield d.isoformat()
        d += datetime.timedelta(days=1)


def main():
    with open(SRC, encoding='utf-8') as fp:
        data = json.load(fp)
    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    byid = {h['id']: h for h in master['hotels']}

    for hid, src in (('h14', SRC_H14), ('h15', SRC_H15)):
        tgt = byid.get(hid)
        if not tgt:
            sys.exit('호텔 없음: %s' % hid)
        old = tgt.get('rates') or {}
        rates = {day: None for day in window_days()}      # 창 안 날짜는 전부 비운 뒤 실측분만 채운다
        for day, krw in (data[hid].get('rates') or {}).items():
            if day not in rates:
                sys.exit('%s 날짜가 창 밖: %s' % (hid, day))
            if not isinstance(krw, (int, float)):
                sys.exit('%s 요금값이 숫자가 아님: %s' % (hid, day))
            rates[day] = int(round(krw))
        tgt['rates'] = rates
        tgt['source'] = src
        n = sum(1 for v in rates.values() if v is not None)
        added = [d for d, v in rates.items() if v is not None and not old.get(d)]
        changed = [(d, old[d], v) for d, v in rates.items() if old.get(d) and v != old[d]]
        dropped = [d for d, v in old.items() if v and rates.get(d) is None]
        print('%s %s — 실측 %d일 / null %d일 · 신규 %d · 정정 %d · 삭제 %d'
              % (hid, tgt['name'], n, len(rates) - n, len(added), len(changed), len(dropped)))
        for d, a, b in changed:
            print('   정정 %s: %s → %s' % (d, format(a, ','), format(b, ',')))
        if dropped:
            print('   !! 기존값이 사라진 날: %s' % dropped[:5])

    if EXT_ADD not in master['extended']:
        master['extended'] = master['extended'] + EXT_ADD
    if SRC_FILE not in master['sources']:
        master['sources'].append(SRC_FILE)

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('merged h14·h15 (최종 보완분)')


if __name__ == '__main__':
    main()
