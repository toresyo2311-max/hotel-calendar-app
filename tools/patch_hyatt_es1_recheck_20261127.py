#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""④ 하얏트 — 스페인 1차 6곳(algtr · alcma · asibz · alsfu · alvfu · secbr) 카드 메모 사유 정정
(2026-11-27 · 값·곳수 변화 없음)

입력
  · 4번(@jin_4) 스페인 1차 교차검증 확정본
      memory/clones/06130525-jin489/pickle/2026-11-27-0539/received/0-hyatt-es1-recheck-6.json
      (numAdults=2 · numChildren=0 · roomQuantity=1 · los=2 · 20일 창 19개 = 6곳 114회 +
       los=7 교차조회 + 공홈 포인트 캘린더 UI 2박·성인2 + 대조군 ascoa)

■ 정정 내용
- 1차 수집은 성인1·1박이었고, 이번 재측정(성인2·2박·los=7·UI)에서도 6곳 전부
  {"days":{},"responseInfo":"soldOutHotel"} · 「이용 가능한 객실 없음」이었다.
- 따라서 이 6곳의 0/365 는 최소숙박·인원 조건 아티팩트가 아니라 **실제 어워드 재고 미표출
  (no_award_inventory_exposed)** 로 확정한다. 같은 조건의 대조군 알루아솔 코스타 아데헤(ascoa)는
  정상 값(15,000P 등)을 반환해 파라미터·날짜·UI 경로 문제가 아님을 확인했다.
- 포인트 값·카테고리·곳수는 그대로다(전부 0칸 · A0/A1/A2 · 560곳).
"""

import io
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(os.path.dirname(ROOT))
TAB = os.path.join(ROOT, 'data', 'app', 'tab10_hyatt.json')
RECHECK = os.path.join(WS, 'memory/clones/06130525-jin489/pickle/2026-11-27-0539/received/'
                           '0-hyatt-es1-recheck-6.json')

CASH = ('현금 요금은 365일 전부 —입니다 — 공홈 세후 KRW 현금은 미수집입니다'
        '(rooms/roomrates 엔드포인트가 404·429로 차단).')

RECHECK_TXT = (
    '1차 수집은 성인1·1박(20일 이하 창 타일링)이었고, 2026-11-27 05:40 KST에 사유를 교차검증'
    '했습니다 — 최소숙박·인원 조건 아티팩트인지 배제하려고 numAdults=2 · numChildren=0 · '
    'roomQuantity=1 · los=2 · 20일 창 19개(호텔당 365일 전량 · 6곳 114회)로 다시 쟀고, 응답 본문이 '
    '전부 빈 days 오브젝트에 responseInfo=soldOutHotel 만 온 응답이었습니다. los=7 교차조회와 공홈 포인트 캘린더 '
    'UI(2박·성인2)에서도 6곳 모두 「이용 가능한 객실 없음」·월 버튼 전부 비활성이었고, 같은 조건의 '
    '대조군 알루아솔 코스타 아데헤(ascoa · 같은 Alua 브랜드)는 15,000P 등 정상 값을 돌려줬습니다 '
    '— 파라미터·날짜·UI 경로 문제가 아닙니다. 그래서 6곳 모두 최소숙박·인원 조건 때문이 아니라 '
    '실제 어워드 재고 미표출(no_award_inventory_exposed)로 확정합니다.'
)

NOTES = {
    'algtr': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:29 KST · hyatt.com · 스페인 알메리아) — 하얏트 '
        '공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)으로 '
        '365칸을 받았고, 공홈 표시 어워드 카테고리는 A0(공홈 표기 A)입니다. 포인트 0일 — 전 기간 '
        '어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 단일·2일 창 재조회(2026-11-28 익일 · 12-01~02 · 12-10~12 · 2027-01-15 · 03-15 · '
        '04-15 · 07-15)도 모두 soldOutHotel이었고 roomCategory 미지정·성인2 조회도 같았습니다(같은 '
        'Alua 브랜드의 알루아솔 이비자도 같은 상태이나 알루아솔 코스타 아데헤는 표출돼 브랜드 전체 '
        '문제는 아닙니다). ' + CASH + ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
    'alcma': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:29 KST · hyatt.com · 스페인 마요르카) — 하얏트 '
        '공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)으로 '
        '365칸을 받았고, 공홈 표시 어워드 카테고리는 A0(공홈 표기 A)입니다. 포인트 0일 — 전 기간 '
        '어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 단일·2일 창 재조회(2026-12-15 · 2027-02-15 · 05-15 · 06-10 · 07-15 · 11-15)도 모두 '
        'soldOutHotel이었습니다. ' + CASH + ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
    'asibz': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:31~20:50 KST · hyatt.com · 스페인 이비자) — 하얏트 '
        '공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)으로 '
        '365칸을 받았고, 공홈 표시 어워드 카테고리는 A1(공홈 캘린더는 B로 표기)입니다. 포인트 0일 '
        '— 전 기간 어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 3~20일 샘플 창 7개(겨울·봄·초여름·성수기·가을)도 모두 {days:{}, '
        '빈 days 오브젝트에 responseInfo=soldOutHotel 만 온 응답이었고 공홈 캘린더는 월 그리드가 뜨지 않고 비활성 버튼이었습니다. '
        + CASH + ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
    'alsfu': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:31~20:50 KST · hyatt.com · 스페인 푸에르테벤투라) '
        '— 하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)'
        '으로 365칸을 받았고, 공홈 표시 어워드 카테고리는 A0(공홈 표기 A)입니다. 포인트 0일 — 전 '
        '기간 어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 시즌별 3~20일 샘플 창 7개(겨울·봄·성수기(los=7 포함)·가을·연말)도 모두 '
        'soldOutHotel이었습니다. ' + CASH + ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
    'alvfu': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:31~20:50 KST · hyatt.com · 스페인 푸에르테벤투라) '
        '— 하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)'
        '으로 365칸을 받았고, 공홈 표시 어워드 카테고리는 A0(공홈 표기 A)입니다. 포인트 0일 — 전 '
        '기간 어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 시즌별 3~20일 샘플 창 6개(겨울·봄·성수기·가을·연말)도 모두 soldOutHotel이었습니다. '
        + CASH + ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
    'secbr': (
        '스탠다드 아워드 365일 실측(2026-11-26 20:39 KST · hyatt.com · 스페인 푸에르테벤투라) — '
        '하얏트 공홈 어워드 응답(/explore-hotels/service/avail/days · roomCategory=STANDARD_ROOM)'
        '으로 365칸을 받았고, 공홈 표시 어워드 카테고리는 A2(공홈 캘린더는 C로 표기)입니다. 포인트 '
        '0일 — 전 기간 어워드가 표출되지 않아 365칸 전부 —입니다. ' + RECHECK_TXT +
        ' 1차 재조회(60일 창 6회 + 5일 창 1회 · 2027-08-10~14 포함)도 모두 soldOutHotel이었고, '
        '공홈 예약(/shop/rooms · 포인트 사용) 화면에서도 「이용 가능한 객실 없음 — 해당 날짜에 '
        '포인트나 어워드로 예약을 받지 않습니다」를 확인했습니다. ' + CASH +
        ' 4번(@jin_4)이 1차 실측·교차검증해 보낸 본입니다.'),
}


def main():
    tab = json.load(open(TAB, encoding='utf-8'))
    hs = {h['code']: h for h in tab['hotels']}
    recheck = json.load(open(RECHECK, encoding='utf-8'))['hotels']
    assert set(recheck) == set(NOTES), sorted(set(recheck) ^ set(NOTES))
    assert len(tab['hotels']) == 560

    for code, h in hs.items():
        if code not in NOTES:
            continue
        r = recheck[code]
        assert h['name'] and h['region'] == '유럽'
        assert h['category'] == r['category'], (code, h['category'], r['category'])
        assert sum(1 for v in h['points']['$v'] if v is not None) == 0, code
        assert sum(1 for v in r['points'].values() if v is not None) == 0, code
        old = h['note']
        assert old.startswith('스탠다드 아워드 365일 실측'), code
        assert '실제 어워드 재고 미표출' not in old, code
        h['note'] = NOTES[code]
        # 개관 전 표기는 달력 UI 가 호텔 전체 미오픈 신호로 읽으므로 쓰지 않는다
        assert '개관 전' not in h['note'], code
        print('%-6s %-6s %-28s %d자 -> %d자' % (code, h['id'], h['name'], len(old), len(h['note'])))

    with io.open(TAB, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(tab, ensure_ascii=False, separators=(',', ':')) + '\n')

    cells = sum(len(h['points']['$v']) for h in tab['hotels'])
    priced = sum(1 for h in tab['hotels'] for v in h['points']['$v'] if v is not None)
    print('hotels %d cells %d priced %d (값·곳수 변화 없음)' % (len(tab['hotels']), cells, priced))
    assert len(tab['hotels']) == 560 and cells == 204400 and priced == 171774


if __name__ == '__main__':
    main()
