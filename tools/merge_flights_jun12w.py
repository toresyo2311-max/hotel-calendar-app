#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""부산 출발 **기존 24개 노선의 2027년 6월 1~2주차(6/3~7 · 6/10~14) 5패턴 240칸** 실측을
`data/master_db.json` 의 `flights` 에 병합한다.

원본 4건(`data-sources/flights-2027-06/pus-24routes-2027-06w12-*.md`, 2026-11-19 KST 실측):
  · `jp-gum`   일본 5 + 괌 1 = 6노선 60칸   (표: 칸 | 날짜(박수) | 전체 최저가 | 직항 최저가)
  · `cn`       중국 본토 5노선 50칸        (표: 칸 | 요일 | 최저가 | 최저 편성 | 직항 최저가)
  · `twhkmo`   대만·홍콩·마카오 5노선 50칸 (표: 패턴 | 최저 왕복총액 | 최저가 조합·소요 | 직항 최저)
  · `sea`      동남아 8노선 80칸           (표: 칸 | 구간(요일·박수) | 최저 왕복 총액 | 항공사 · 경유 | 직항 최저)

규칙:
  · 240칸 모두 `routes[].deals` 에 넣는다(`price` = 원문 금액 그대로, 반올림 없음).
  · 이 격자에 **이미 있던 '가격표' 자리표시 칸**(`src: 가격표`, 직항/경유 미확인)은 같은 노선·출발일·
    패턴이므로 이번 실측값으로 **교체**한다(같은 칸을 두 값으로 두지 않는다). 교체 대상이 아닌
    칸(0박 당일치기 등)은 건드리지 않는다.
  · `via` 는 그 칸 **최저가 편성**이 직항(`false`)·경유(`true`)인지로 적고, 편성 자체가 화면에
    표시되지 않은 칸(최저가 탭 OTA 요금)은 `null` 로 둔다(추정하지 않는다).
  · `note` 는 기존 앱 표기(`직항 1시간 10분 (14:50 출발)`,
    `경유 1회(선양) · 환승 2시간 30분 · 총 7시간 20분 (11:20-17:40)`) 꼴로 적는다 — 앱의 장시간
    경유 배지가 note 의 `환승 N시간` 을 읽어 12h+/20h+ 를 계산한다(flDur/flLongClass).
  · `alt` 는 그 칸 직항 최저가가 최저가보다 비쌀 때만 넣는다(앱이 '직항 …원'으로 병기).
  · 제3자 사이트 이름(원본의 `[출처: …]`·URL)은 값·note·화면 문구 어디에도 넣지 않는다.
  · 호텔 538곳 · 아코르 · ⑥ 땡처리 · 출처 목록 · 패턴/주차 정의 · 다른 노선/기존 딜·`noSale` 은
    값 대조로 보존을 확인한다.
  · `counts`(total · byMonth · holiday · daytrip)를 다시 세고, 2027-06 `notes` 끝에 이번 병합
    문장을 덧붙인다(plain text — `**` 금지). `extended` 끝에 한 줄을 덧붙인다(`--note`).

사용법 (저장소 루트에서):
    python3 tools/merge_flights_jun12w.py --dump-cells
    python3 tools/merge_flights_jun12w.py --dry-run
    python3 tools/merge_flights_jun12w.py
"""
import argparse
import collections
import datetime
import decimal
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.path.normpath(os.path.join(ROOT, '..', '..', 'data-sources', 'flights-2027-06'))
FILES = {
    'jp': 'pus-24routes-2027-06w12-jp-gum.md',
    'cn': 'pus-24routes-2027-06w12-cn.md',
    'tw': 'pus-24routes-2027-06w12-twhkmo.md',
    'sea': 'pus-24routes-2027-06w12-sea.md',
}

WD = {'월': 0, '화': 1, '수': 2, '목': 3, '금': 4, '토': 5, '일': 6}   # datetime.weekday()
PAT_NIGHTS = {'금~일': 2, '토~월': 2, '목~일': 3, '금~월': 3, '목~월': 4}
WEEK_THU = ('2027-06-03', '2027-06-10')
WEEK_LABEL = {'2027-06-03': '6/3~7', '2027-06-10': '6/10~14'}
MONTH = '2027-06'
GRID_START, GRID_END = '2027-06-03', '2027-06-14'
HOLIDAY_DATES = ('2026-12-25', '2027-02-04')

CITY = {'FUK': '후쿠오카', 'KIX': '오사카', 'TYO': '도쿄', 'NGO': '나고야', 'OKA': '오키나와',
        'GUM': '괌', 'PVG': '상하이', 'BJS': '베이징', 'NKG': '난징', 'HGH': '항저우',
        'TAO': '칭다오', 'TPE': '타이베이', 'HKG': '홍콩', 'KHH': '가오슝', 'RMQ': '타이중',
        'MFM': '마카오', 'BKK': '방콕', 'CNX': '치앙마이', 'DAD': '다낭', 'CXR': '나트랑',
        'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르', 'DPS': '발리'}
ROUTES = ('FUK', 'KIX', 'TYO', 'NGO', 'OKA', 'GUM',          # 일본 5 + 괌 1
          'PVG', 'BJS', 'NKG', 'HGH', 'TAO',                  # 중국 본토 5
          'TPE', 'HKG', 'KHH', 'RMQ', 'MFM',                  # 대만·홍콩·마카오 5
          'BKK', 'CNX', 'DAD', 'CXR', 'HAN', 'SGN', 'SIN', 'DPS')   # 동남아 8
SRC_ROUTES = {'jp': ROUTES[:6], 'cn': ROUTES[6:11], 'tw': ROUTES[11:16], 'sea': ROUTES[16:]}

# 원본 4건의 집계 — 파서가 같은 숫자를 내는지 대조한다(노선별 최저·최고는 원본 요약표와 직접 대조)
EXPECT_GRID = 240                 # 24노선 × 2주 × 5패턴
EXPECT_PLACEHOLDER = 77           # 이 격자에 남아 있던 '가격표' 자리표시(교체 대상)
EXPECT_NEW = 163                 # 이번에 새로 넣는 칸(240 - 77)
EXPECT_OVERALL = (262460, 849300)   # 타이베이 6/10~10 ~ 마카오 6/3~6·6/4~6
EXPECT_AVG = 461518
EXPECT_DIRECT = 91               # 최저가가 직항인 칸
EXPECT_ALT = 36                  # 직항 금액을 병기한 칸
EXPECT_UNKNOWN = (('TAO', '2027-06-04', '금~일'),)   # 편성 미확인(최저가 탭 OTA 금액)
EXPECT_WEEK_AVG = {'2027-06-03': 463374, '2027-06-10': 459662}
EXPECT_PAT_AVG = {'금~일': 462616, '토~월': 451693, '목~일': 476612,
                  '금~월': 443997, '목~월': 472672}
EXPECT_LONG = (6, 2)             # 환승 12시간 이상 6칸(그중 20시간 이상 2칸)
EXPECT_GRID_ROUTE = {
    'FUK': (333438, 415000), 'KIX': (351679, 381550), 'TYO': (482300, 564691),
    'NGO': (477275, 554381), 'OKA': (462000, 713000), 'GUM': (645400, 733100),
    'PVG': (285919, 444335), 'BJS': (465865, 479900), 'NKG': (480736, 569500),
    'HGH': (480730, 689500), 'TAO': (473400, 548700),
    'TPE': (262460, 310760), 'HKG': (347070, 431200), 'KHH': (399700, 506000),
    'RMQ': (403100, 544100), 'MFM': (538700, 849300),
    'BKK': (354623, 365112), 'CNX': (328401, 662100), 'DAD': (331573, 500995),
    'CXR': (351213, 378375), 'HAN': (281016, 299331), 'SGN': (279571, 279571),
    'SIN': (464200, 715439), 'DPS': (434500, 586037),
}

BANNED = ('트립', 'trip.com', '스카이스캐너', 'Skyscanner', '카약', 'Kayak', '구글', 'Google',
          '네이버', 'naver', '아고다', '부킹', 'Booking', '호텔스컴바인', '마이리얼트립',
          '야놀자', '여기어때', '익스피디아', 'Expedia', '출처')
# 원본이 쓰는 항공사 표기를 앱 표기로 다듬는다(뜻은 그대로)
AIRLINE_FIX = {'이스타': '이스타항공', '홍콩익스프레스': '홍콩 익스프레스항공',
               '홍콩익스프레스항공': '홍콩 익스프레스항공',
               '홍콩익스프레스+캐세이패시픽': '홍콩 익스프레스항공+캐세이패시픽항공'}


def rnd(x):
    """보고서와 같은 반올림(0.5 올림)."""
    return int(decimal.Decimal(str(x)).quantize(0, rounding=decimal.ROUND_HALF_UP))


def won(text):
    m = re.search(r'([\d,]{4,})', text)
    return int(m.group(1).replace(',', '')) if m else None


def fmt_dur(text):
    """'1시간10분' / '2h20' / '28h' / '30시간' → '1시간 10분' / '2시간 20분' / '28시간'."""
    if text is None:
        return None
    text = text.strip()
    m = re.fullmatch(r'(\d+)\s*h\s*(\d+)?', text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        return '%d시간' % h + (' %02d분' % mi if mi else '')
    m = re.fullmatch(r'(\d+)\s*시간\s*(\d+)?\s*분?', text)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        return '%d시간' % h + (' %02d분' % mi if mi else '')
    m = re.fullmatch(r'(\d+)\s*분', text)
    if m:
        return '%02d분' % int(m.group(1))
    raise SystemExit('소요시간 형식 이상: %r' % text)


HUB_KO = {'ICN': '인천', 'GMP': '김포', 'PVG': '상하이', 'HKG': '홍콩', 'TPE': '타이베이',
          'SGN': '호찌민', 'DAD': '다낭', 'HAN': '하노이', 'MNL': '마닐라', 'BKK': '방콕',
          'KUL': '쿠알라룸푸르', 'PEK': '베이징', 'NKG': '난징', 'TAO': '칭다오'}


def hub_ko(text):
    """경유지 표기 — 원본이 공항 코드로 적은 칸은 코드 그대로 둔다(같은 노선 앞선 주차와 같은 꼴)."""
    return text.strip()


def fmt_times(text):
    """'PUS 15:50 → PVG 16:50' / '08:10→14:45' / '08:10 출발' / '14:50' → '15:50-16:50' 등."""
    text = text.strip()
    m = re.search(r'(\d\d:\d\d)\s*→\s*(\d\d:\d\d(?:\+\d)?)', text)
    if m:
        return m.group(1) + '-' + m.group(2)
    m = re.search(r'(\d\d:\d\d)\s*출발', text)
    if m:
        return m.group(1) + ' 출발'
    m = re.search(r'(\d\d:\d\d)\s*$', text)
    if m:
        return m.group(1) + ' 출발'
    return None


def lay_min(note):
    """note 의 '환승 N시간 N분' → 분(없으면 None)."""
    m = re.search(r'환승\s*(\d+)시간\s*(?:(\d+)분)?', note or '')
    return (int(m.group(1)) * 60 + int(m.group(2) or 0)) if m else None


def total_min(note):
    """note 의 '총 N시간 N분' → 분(없으면 None)."""
    m = re.search(r'총\s*(\d+)시간\s*(?:(\d+)분)?', note or '')
    return (int(m.group(1)) * 60 + int(m.group(2) or 0)) if m else None


# ---------------------------------------------------------------- 원본별 파서
def read(key):
    path = os.path.join(SRC, FILES[key])
    if not os.path.isfile(path):
        raise SystemExit('원본이 없습니다: %s' % path)
    return open(path, encoding='utf-8').read()


def cell(code, date, back, pattern, price, airline, via, note, alt=None):
    if pattern not in PAT_NIGHTS:
        raise SystemExit('%s %s 알 수 없는 패턴 %r' % (code, date, pattern))
    d = datetime.date.fromisoformat(date)
    b = datetime.date.fromisoformat(back)
    if (b - d).days != PAT_NIGHTS[pattern]:
        raise SystemExit('%s %s 박수 불일치 %s (%s~%s)' % (code, pattern, PAT_NIGHTS[pattern],
                                                        date, back))
    if WD[pattern[0]] != d.weekday():
        raise SystemExit('%s %s 요일 불일치 (%s)' % (code, date, pattern))
    if WD[pattern[-1]] != b.weekday():
        raise SystemExit('%s %s 귀국 요일 불일치 (%s)' % (code, back, pattern))
    if not (GRID_START <= date <= GRID_END):
        raise SystemExit('%s 출발일이 이번 범위 밖: %s' % (code, date))
    if not price or price <= 0:
        raise SystemExit('%s %s 금액이 양의 정수가 아닙니다: %r' % (code, date, price))
    if airline:
        airline = AIRLINE_FIX.get(airline, airline)
    return dict(code=code, date=date, back=back, pattern=pattern, price=price,
                airline=airline or None, via=via, alt=alt, note=note)


def parse_jp():
    """일본 5 + 괌 — ```table 블록의 `["칸", "목~일 06/03~06/06 (3박4일)", 전체 최저가, 직항 최저가]`."""
    cells, code = {}, None
    for line in read('jp').splitlines():
        m = re.match(r'^title:\s*([A-Z]{3})\s+부산', line.strip())
        if line.strip().startswith('title:'):
            code = m.group(1) if m else None
            if code is not None and code not in ROUTES:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        s = line.strip()
        if not s.startswith('- ["'):
            continue
        if code is None:
            continue          # 노선 표가 아닌 블록(노선 요약·달력)
        row = json.loads(s[2:])
        if len(row) == 4 and re.fullmatch(r'\d+/\d+칸', row[1]):
            continue          # 위쪽 '노선 요약' 표(노선·칸수·최저~최고·직항)는 칸이 아니다
        if len(row) != 4:
            raise SystemExit('%s 칸 형식 이상: %r' % (code, row))
        dm = re.match(r'^([월화수목금토일]~[월화수목금토일])\s+'
                      r'(\d\d/\d\d)~(\d\d/\d\d)\s*\((\d)박\d일\)$', row[1])
        if not dm:
            raise SystemExit('%s 날짜를 읽지 못했습니다: %r' % (code, row[1]))
        pat = dm.group(1)
        date = '2027-' + dm.group(2).replace('/', '-')
        back = '2027-' + dm.group(3).replace('/', '-')
        if PAT_NIGHTS[pat] != int(dm.group(4)):
            raise SystemExit('%s 박수 표기 불일치: %r' % (code, row[1]))
        best = row[2].replace('★최저', '').strip()
        price = won(best)
        if not price:
            raise SystemExit('%s 최저가를 읽지 못했습니다: %r' % (code, best))
        parts = [x.strip() for x in best.split(' · ')]
        comp = parts[1] if len(parts) > 1 else ''
        comp = comp.replace('(직항 필터)', '').strip()      # '직항(직항 필터)' = 직항 필터로 확인
        cm = re.match(r'^(\S+)\s+(직항|1회)\s*(.*)$', comp)
        if not cm:
            raise SystemExit('%s 편성을 읽지 못했습니다: %r' % (code, comp))
        airline, kind, dur = cm.group(1), cm.group(2), cm.group(3).strip()
        if len(parts) > 2:
            raise SystemExit('%s 처리하지 못한 최저가 비고: %r' % (code, parts[2:]))
        direct = row[3].replace('(같은 편)', '').strip()
        alt = None
        if direct.startswith('직항 0건'):
            dp = None
        else:
            dp = won(direct)
            if not dp:
                raise SystemExit('%s 직항 최저가를 읽지 못했습니다: %r' % (code, direct))
            if dp > price:
                alt = dp
        if kind == '직항':
            note = '직항'
            if dur:
                note += ' ' + fmt_dur(dur)
            if direct.startswith('₩'):
                tail = direct.split(' · ', 1)
                if len(tail) > 1:
                    t = fmt_times(tail[1])
                    if t:
                        note += ' (' + t + ')'
            via = False
        else:
            note = '경유 1회(경유지 미표기)'
            if dur:
                note += ' · 총 ' + fmt_dur(dur)
            else:
                note += ' · 총 소요시간 미표기'
            via = True
        if alt is not None and via is False:
            alt = None          # 최저가 자체가 직항 — 직항 금액을 겹쳐 적지 않는다
        if alt is not None and alt <= price:
            raise SystemExit('%s 직항 금액이 최저가 이하: %s %s (%s <= %s)'
                             % (code, row[1], date, alt, price))
        cells[(code, date, pat)] = cell(code, date, back, pat, price, airline, via, note, alt)
    return cells


def parse_cn():
    """중국 본토 5노선 — 노선 절(`## 🛫 …(PVG…)`) 아래 `| 06/03~06/06 | 목~일 | 금액 | 편성 | 직항 |`."""
    cells, code = {}, None
    for line in read('cn').splitlines():
        s = line.strip()
        m = re.match(r'^##\s*🛫\s*부산\(PUS\).*?\(([A-Z]{3})', s)
        if m:
            code = m.group(1)
            if code not in SRC_ROUTES['cn']:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        if s.startswith('## '):
            code = None
        if not s.startswith('| 06/'):
            continue
        if code is None:
            raise SystemExit('노선 없이 칸: %s' % s[:80])
        cols = [c.strip() for c in s.strip('|').split('|')]
        if len(cols) != 5:
            raise SystemExit('%s 칸 열 수 %d: %r' % (code, len(cols), cols))
        dm = re.match(r'^(\d\d/\d\d)~(\d\d/\d\d)$', cols[0])
        if not dm:
            raise SystemExit('%s 날짜를 읽지 못했습니다: %r' % (code, cols[0]))
        date = '2027-' + dm.group(1).replace('/', '-')
        back = '2027-' + dm.group(2).replace('/', '-')
        pat = cols[1]
        price = won(cols[2])
        if not price:
            raise SystemExit('%s 금액을 읽지 못했습니다: %r' % (code, cols[2]))
        airline, via, note = parse_cn_comp(code, cols[3])
        # 직항 최저가 열 — 최저가보다 비싼 직항 값만 alt 로 병기한다
        alt = None
        dcol = cols[4]
        if dcol.startswith('직항 0건'):
            pass
        elif dcol.startswith('₩'):
            dp = won(dcol)
            if dp and dp > price:
                alt = dp
            elif dp and dp < price:
                print('  [참고] %s %s 직항 최저 %s 가 최저가 %s 보다 쌉니다 — alt 생략'
                      % (code, date, format(dp, ','), format(price, ',')))
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, dcol))
        cells[(code, date, pat)] = cell(code, date, back, pat, price, airline, via, note, alt)
    return cells


def parse_cn_comp(code, text):
    """'대한항공 **직항** 2시간 (PUS 15:50 → PVG 16:50)' / '중국남방항공 1회경유(선양 2시간30분) 7시간20분 (…)'. """
    raw = text
    m = re.match(r'^(\S+)\s+\*\*직항\*\*\s*(.*)$', text)
    if m:
        airline, rest = m.group(1), m.group(2)
        dur = None
        dm = re.match(r'^(\d+시간(?:\s*\d+분)?)', rest)
        if dm:
            dur = dm.group(1)
            rest = rest[dm.end():].strip()
        times = fmt_times(rest)
        note = '직항' + ((' ' + fmt_dur(dur)) if dur else '')
        if times:
            note += ' (' + times + ')'
        return airline, False, note

    m = re.match(r'^(\S+)\s+(1회경유|자가환승)\(([^)]*)\)\s*(.*)$', text)
    if m:
        airline, kind, inner, rest = m.group(1), m.group(2), m.group(3), m.group(4)
        hub, lay = inner.strip(), None
        lm = re.search(r'(\d+시간\s*\d*\s*분?)\s*$', hub)
        if lm:
            lay = fmt_dur(lm.group(1))
            hub = hub[:lm.start()].strip()
        total = None
        tm = re.match(r'^(\d+시간(?:\s*\d+분)?)?', rest)
        if tm.group(1):
            total = fmt_dur(tm.group(1))
            rest = rest[tm.end():].strip()
        times = None
        pm = re.search(r'[\(（]([^)）]*)[\)）]', rest)
        if pm:
            times = fmt_times(pm.group(1))
            rest = rest.replace(pm.group(0), '')
        else:
            dm = re.search(r'PUS\s+\d\d:\d\d\s+출발', rest)
            if dm:
                times = fmt_times(dm.group(0))
                rest = rest.replace(dm.group(0), '')
        rest = rest.strip().strip('·').strip()
        extras = [x.strip() for x in rest.split(' · ') if x.strip()]
        extras = [x for x in extras if x not in ('다구간 표시',)
                  and not x.startswith('→') and not x.startswith('목록 최저')
                  and not x.startswith('최저 표시')]
        if extras:
            print('  [참고] %s 부가 비고를 note 에 넣지 않습니다: %r' % (code, extras))
        if kind == '자가환승':
            note = '자가환승(%s)' % hub if hub else '자가환승(경유지 미표기)'
        else:
            note = '경유 1회' + ('(%s)' % hub if hub else '(경유지 미표기)')
        if lay:
            note += ' · 환승 ' + lay
        if total:
            note += ' · 총 ' + total
        else:
            note += ' · 총 소요시간 미표기'
        if times:
            note += ' (' + times + ')'
        return airline, True, note

    if text.startswith('최저가 탭 OTA 요금'):
        return None, None, '직항/경유 미확인 · 최저가 탭 금액(편성 미표시)'
    raise SystemExit('%s 편성을 읽지 못했습니다: %r' % (code, text))


def parse_tw():
    """대만·홍콩·마카오 — ```table 블록의 `[1주 목~일 06-03~06, ₩292,248, 편성, 직항 최저]`."""
    cells, code = {}, None
    for line in read('tw').splitlines():
        s = line.strip()
        m = re.match(r'^##\s.*?\(([A-Z]{3})\)', s)
        if m:
            code = m.group(1)
            if code not in SRC_ROUTES['tw']:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        if not s.startswith('- ['):
            continue
        if code is None:
            continue          # 노선 절 밖(노선 요약·출처 목록)
        body = s[3:].strip()
        if not body.endswith(']'):
            raise SystemExit('%s 행 형식 이상: %r' % (code, s))
        row = [x.strip() for x in body[:-1].split(', ')]
        if len(row) != 4:
            raise SystemExit('%s 행 열 수 %d: %r' % (code, len(row), row))
        dm = re.match(r'^[12]주\s+([월화수목금토일]~[월화수목금토일])\s+(\d\d)-(\d\d)~(\d\d)$',
                      row[0])
        if not dm:
            raise SystemExit('%s 날짜를 읽지 못했습니다: %r' % (code, row[0]))
        pat = dm.group(1)
        date = '2027-%s-%s' % (dm.group(2), dm.group(3))
        back = '2027-%s-%s' % (dm.group(2), dm.group(4))
        price = won(row[1])
        if not price:
            raise SystemExit('%s 금액을 읽지 못했습니다: %r' % (code, row[1]))
        airline, via, note = parse_tw_comp(code, row[2])
        dcol = row[3].replace('†', '').strip()
        alt = None
        if dcol.startswith('₩'):
            dp = won(dcol)
            if dp > price and via is True:
                alt = dp
        elif '직항 없음' in dcol or '가격 미제공' in dcol or dcol == '동일':
            pass
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, dcol))
        cells[(code, date, pat)] = cell(code, date, back, pat, price, airline, via, note, alt)
    return cells


def parse_tw_comp(code, text):
    if text.startswith('최저가 탭'):
        return None, None, '직항/경유 미확인 · 최저가 탭 금액(편성 미표시)'
    parts = [x.strip() for x in text.split(' · ')]
    if len(parts) < 2:
        raise SystemExit('%s 편성을 읽지 못했습니다: %r' % (code, text))
    airline, kind = parts[0], parts[1]
    dur = fmt_dur(parts[2]) if len(parts) > 2 else None
    if len(parts) > 3:
        raise SystemExit('%s 처리하지 못한 편성 비고: %r' % (code, text))
    if kind == '직항':
        return airline, False, '직항' + ((' ' + dur) if dur else '')
    m = re.match(r'^([A-Z]{3})\s+(\d)회$', kind)
    if not m:
        raise SystemExit('%s 편성 문구를 읽지 못했습니다: %r' % (code, kind))
    note = '경유 %s회(%s)' % (m.group(2), hub_ko(m.group(1)))
    if dur:
        note += ' · 총 ' + dur
    return airline, True, note


def parse_sea():
    """동남아 8노선 — 노선 절(`### 1. 🇹🇭 방콕 (BKK) …`) 아래
    `| S01 | 06/03~06/06 (목~일 3박4일) | 금액 [출처…] | 항공사 · 경유 | 직항 최저 |`."""
    cells, code = {}, None
    for line in read('sea').splitlines():
        s = line.strip()
        m = re.match(r'^###\s*\d+\.\s.*?\(([A-Z]{3})\)', s)
        if m:
            code = m.group(1)
            if code not in SRC_ROUTES['sea']:
                raise SystemExit('알 수 없는 노선 %s' % code)
            continue
        if s.startswith('## ') or s.startswith('### '):
            code = None
        if not s.startswith('| S'):
            continue
        if code is None:
            continue          # 노선 절 밖(1주차 vs 2주차 요약)
        cols = [c.strip() for c in s.strip('|').split('|')]
        if len(cols) != 5:
            raise SystemExit('%s 칸 열 수 %d: %r' % (code, len(cols), cols))
        dm = re.match(r'^(\d\d/\d\d)~(\d\d/\d\d)\s*\(([월화수목금토일]~[월화수목금토일])'
                      r'\s*(\d)박\d일\)$', cols[1])
        if not dm:
            raise SystemExit('%s 구간을 읽지 못했습니다: %r' % (code, cols[1]))
        date = '2027-' + dm.group(1).replace('/', '-')
        back = '2027-' + dm.group(2).replace('/', '-')
        pat = dm.group(3)
        if PAT_NIGHTS[pat] != int(dm.group(4)):
            raise SystemExit('%s 박수 표기 불일치: %r' % (code, cols[1]))
        price = won(cols[2])
        if not price:
            raise SystemExit('%s 금액을 읽지 못했습니다: %r' % (code, cols[2]))
        airline, via, note = parse_sea_comp(code, cols[3])
        dcol = cols[4].replace('†', '').replace('‡', '').strip()
        alt = None
        if dcol == '0건':
            pass
        elif dcol.startswith('₩'):
            dp = won(dcol)
            if dp > price and via is True:
                alt = dp
            elif dp < price:
                print('  [참고] %s %s 직항 최저 %s 가 최저가 %s 보다 쌉니다 — alt 생략'
                      % (code, date, format(dp, ','), format(price, ',')))
        else:
            raise SystemExit('%s 직항 열을 읽지 못했습니다: %r' % (code, dcol))
        cells[(code, date, pat)] = cell(code, date, back, pat, price, airline, via, note, alt)
    return cells


def parse_sea_comp(code, text):
    if text.startswith('최저가 탭'):
        return None, None, '직항/경유 미확인 · 최저가 탭 금액(편성 미표시)'
    parts = [x.strip() for x in text.split(' · ')]
    if len(parts) < 2:
        raise SystemExit('%s 편성을 읽지 못했습니다: %r' % (code, text))
    airline, kind = parts[0], parts[1]
    if kind == '직항':
        dur = fmt_dur(parts[2].split(' ')[0]) if len(parts) > 2 else None
        times = fmt_times(parts[2]) if len(parts) > 2 else None
        note = '직항' + ((' ' + dur) if dur else '')
        if times:
            note += ' (' + times + ')'
        if len(parts) > 3:
            raise SystemExit('%s 처리하지 못한 편성 비고: %r' % (code, parts[3:]))
        return airline, False, note
    m = re.match(r'^경유(\d)\s+([A-Z]{3})$', kind)
    if m:
        dur = fmt_dur(parts[2].split(' ')[0]) if len(parts) > 2 else None
        times = fmt_times(parts[2]) if len(parts) > 2 else None
        note = '경유 %s회(%s)' % (m.group(1), hub_ko(m.group(2)))
        if dur:
            note += ' · 총 ' + dur
        if times:
            note += ' (' + times + ')'
        if len(parts) > 3:
            raise SystemExit('%s 처리하지 못한 편성 비고: %r' % (code, parts[3:]))
        return airline, True, note
    if kind.startswith('가는편 직항'):
        # 가는편만 직항, 오는편은 직항 미운항 — 왕복 논스톱이 아니라 경유로 센다
        tm = re.search(r'\((\d+시간\s*\d*\s*분)?\s*(\d\d:\d\d)→(\d\d:\d\d)\)', kind)
        note = '가는편 직항'
        if tm and tm.group(1):
            note += ' ' + fmt_dur(tm.group(1))
        if tm:
            note += ' (%s-%s)' % (tm.group(2), tm.group(3))
        note += ' · 오는편 직항 미운항'
        return airline, True, note
    raise SystemExit('%s 편성 문구를 읽지 못했습니다: %r' % (code, kind))


# ---------------------------------------------------------------- 원본 요약표 대조
def summary_jp():
    """`노선 요약` 표 — 노선별 (최저, 최고)."""
    out, inblock = {}, False
    for line in read('jp').splitlines():
        s = line.strip()
        if s.startswith('title: 노선 요약'):
            inblock = True
            continue
        if inblock and s == '```':
            break
        if inblock and s.startswith('- ['):
            row = json.loads(s[2:])
            code = re.search(r'([A-Z]{3})\s', row[0] + ' ').group(1)
            lo, hi = [int(x.replace('₩', '').replace(',', '')) for x in row[2].split('~')]
            out[code] = (lo, hi)
    return out


def summary_cn():
    """노선 절의 `- **10칸 최저 ₩285,919 ~ 최고 ₩444,335**` — 노선별 (최저, 최고)."""
    out, code = {}, None
    for line in read('cn').splitlines():
        s = line.strip()
        m = re.match(r'^##\s*🛫\s*부산\(PUS\).*?\(([A-Z]{3})', s)
        if m:
            code = m.group(1)
            continue
        m = re.search(r'\*\*10칸 최저 ₩([\d,]+) ~ 최고 ₩([\d,]+)\*\*', s)
        if m and code:
            out[code] = (int(m.group(1).replace(',', '')), int(m.group(2).replace(',', '')))
    return out


def summary_tw():
    out = {}
    for line in read('tw').splitlines():
        s = line.strip()
        if not s.startswith('- ['):
            continue
        row = [x.strip() for x in s[3:-1].split(', ')]
        if len(row) != 4 or '₩' not in row[1]:
            continue
        code = re.search(r'([A-Z]{3})$', row[0])
        if not code:
            continue
        out[code.group(1)] = (won(row[1]), won(row[2]))
    return out


def summary_sea():
    out = {}
    for line in read('sea').splitlines():
        s = line.strip()
        m = re.match(r'^\|\s*[^|]*\(([A-Z]{3})\)\s*\|\s*\*\*₩([\d,]+)\*\*\s*\|.*\|\s*₩([\d,]+)\s*\|',
                     s)
        if m:
            out[m.group(1)] = (int(m.group(2).replace(',', '')), int(m.group(3).replace(',', '')))
    return out


def check(cells):
    if len(cells) != 240:
        raise SystemExit('%d칸 (기대 240칸)' % len(cells))
    codes = {k[0] for k in cells}
    if codes != set(ROUTES):
        raise SystemExit('노선이 24개가 아닙니다: %s' % sorted(codes ^ set(ROUTES)))
    for code in ROUTES:
        n = sum(1 for k in cells if k[0] == code)
        if n != 10:
            raise SystemExit('%s %d칸 (기대 10칸)' % (code, n))
    for name, fn in (('일본·괌', summary_jp), ('중국', summary_cn),
                     ('대만·홍콩·마카오', summary_tw), ('동남아', summary_sea)):
        exp = fn()
        if not exp:
            raise SystemExit('%s 요약표를 읽지 못했습니다' % name)
        for code, (lo, hi) in exp.items():
            v = [c['price'] for k, c in cells.items() if k[0] == code]
            if (min(v), max(v)) != (lo, hi):
                raise SystemExit('%s %s 최저·최고 %s (요약표 %s)'
                                 % (name, code, (min(v), max(v)), (lo, hi)))
    # 직항/경유는 요약 문장이 말한 칸수와 맞는지 (동남아 노선별 직항 칸수)
    sea_direct, cur = {}, None
    for line in read('sea').splitlines():
        s = line.strip()
        m = re.match(r'^###\s*\d+\.\s.*?\(([A-Z]{3})\)', s)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'^\*\*직항\(논스톱\):\s*(?:0건|(\d+)/10칸)\*\*', s)
        if m and cur:
            sea_direct[cur] = int(m.group(1) or 0)
    if set(sea_direct) != set(SRC_ROUTES['sea']):
        raise SystemExit('동남아 직항 요약을 읽지 못했습니다: %s' % sorted(sea_direct))
    for code, n in summary_jp_direct().items():
        got = sum(1 for k, c in cells.items()
                  if k[0] == code and (c['via'] is False or c['alt'] is not None))
        if got != n:
            raise SystemExit('일본·괌 %s 직항이 있는 칸 %d (요약표 %d)' % (code, got, n))
    # 동남아 원본의 1주차·2주차 평균(₩410,543 · ₩418,659)
    for thu, want in (('2027-06-03', 410543), ('2027-06-10', 418659)):
        v = [c['price'] for k, c in cells.items() if k[0] in SRC_ROUTES['sea']
             and (datetime.date.fromisoformat(k[1]) - datetime.timedelta(
                 days=(datetime.date.fromisoformat(k[1]).weekday() - WD['목']) % 7)).isoformat()
             == thu]
        if len(v) != 40:
            raise SystemExit('동남아 %s %d칸 (기대 40칸)' % (thu, len(v)))
        if abs(rnd(sum(v) / len(v)) - want) > 1:
            raise SystemExit('동남아 %s 평균 %d (원본 %d)' % (thu, rnd(sum(v) / len(v)), want))
    # 직항이 있는 칸수(원본의 `직항(논스톱): N/10칸`) — 최저가가 직항인 칸 + 직항 금액을 병기한 칸
    for code in SRC_ROUTES['sea']:
        got = sum(1 for k, c in cells.items()
                  if k[0] == code and (c['via'] is False or c['alt'] is not None))
        if got != sea_direct[code]:
            raise SystemExit('동남아 %s 직항이 있는 칸 %d (원본 %d)'
                             % (code, got, sea_direct[code]))
    for k, c in cells.items():
        note = c['note']
        if '**' in note or '[' in note or '출처' in note:
            raise SystemExit('%s note 에 마크업이 있습니다: %r' % (k, note))
        for word in BANNED:
            if word in note or word in (c['airline'] or ''):
                raise SystemExit('%s 값에 제3자 사이트 이름(%s)이 있습니다' % (k, word))
        if c['via'] is True and not any(w in note for w in ('총', '미운항', '편성 미표시')):
            raise SystemExit('%s 경유 칸에 총 소요시간이 없습니다: %r' % (k, note))
        if c['via'] is False and '직항' not in note:
            raise SystemExit('%s 직항 칸 note 이상: %r' % (k, note))
        if c['alt'] is not None and c['alt'] <= c['price']:
            raise SystemExit('%s 직항 금액이 최저가 이하입니다' % (k,))
    return cells


def summary_jp_direct():
    """일본·괌 `노선 요약` 표의 '직항 판매 칸'(n/10칸) — 노선별 직항 운임이 있는 칸수."""
    out, inblock = {}, False
    for line in read('jp').splitlines():
        s = line.strip()
        if s.startswith('title: 노선 요약'):
            inblock = True
            continue
        if inblock and s == '```':
            break
        if inblock and s.startswith('- ['):
            row = json.loads(s[2:])
            code = re.search(r'([A-Z]{3})\s', row[0] + ' ').group(1)
            m = re.match(r'^(\d+)/10칸$', row[1])
            if not m:
                raise SystemExit('%s 직항 판매 칸 표기를 읽지 못했습니다: %r' % (code, row[1]))
            out[code] = int(m.group(1))
    return out


def load():
    cells = {}
    for key, fn in (('jp', parse_jp), ('cn', parse_cn), ('tw', parse_tw), ('sea', parse_sea)):
        part = fn()
        if {c['code'] for c in part.values()} != set(SRC_ROUTES[key]):
            raise SystemExit('%s 노선 집합이 다릅니다: %s'
                             % (key, sorted({c['code'] for c in part.values()})))
        for k in part:
            if k in cells:
                raise SystemExit('중복 칸 %s' % (k,))
        cells.update(part)
        print('%s: %d칸' % (FILES[key], len(part)))
    # 노선 전체에 직항 운임이 한 칸도 없는 노선(원본이 `직항 0건`으로 확인한 노선)은 편성이
    # 표시되지 않은 칸도 경유로 적는다 — 그 노선에는 왕복 논스톱 편 자체가 없다.
    # 직항이 있는 노선의 미표시 칸은 추정하지 않고 `via: null` 로 남긴다.
    for code in ROUTES:
        rc = [c for k, c in cells.items() if k[0] == code]
        if any(c['via'] is False or c['alt'] is not None for c in rc):
            continue
        for c in rc:
            if c['via'] is None:
                c['via'] = True
                c['note'] = '경유 · 편성 미표시(최저가 탭 금액)'
    return check(cells)


def main(argv):
    ap = argparse.ArgumentParser(description='2027년 6월 1~2주(6/3~14) 240칸 → flights 병합')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--dump-cells', action='store_true')
    ap.add_argument('--note', default=None)
    args = ap.parse_args(argv)

    cells = load()
    ps = [c['price'] for c in cells.values()]
    direct = sum(1 for c in cells.values() if c['via'] is False)
    via = sum(1 for c in cells.values() if c['via'] is True)
    unknown = sum(1 for c in cells.values() if c['via'] is None)
    alts = sum(1 for c in cells.values() if c['alt'])
    print('파싱 %d칸 — 최저 %s · 최고 %s · 평균 %s' % (len(cells), format(min(ps), ','),
                                                 format(max(ps), ','),
                                                 format(rnd(sum(ps) / len(ps)), ',')))
    print('직항이 최저가인 칸 %d · 경유 %d · 편성 미확인 %d · 직항 금액 병기 %d'
          % (direct, via, unknown, alts))
    by_route = collections.defaultdict(list)
    by_pat = collections.defaultdict(list)
    by_week = collections.defaultdict(list)
    for (code, date, pat), c in cells.items():
        by_route[code].append(c['price'])
        by_pat[pat].append(c['price'])
        dt = datetime.date.fromisoformat(date)
        by_week[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(c['price'])
    for code in ROUTES:
        v = by_route[code]
        print('  %-3s %2d칸 %9s ~ %9s 평균 %9s'
              % (code, len(v), format(min(v), ','), format(max(v), ','),
                 format(rnd(sum(v) / len(v)), ',')))
    print('주차 평균 ' + ' · '.join('%s %s' % (WEEK_LABEL[k], format(rnd(sum(v) / len(v)), ','))
                                for k, v in sorted(by_week.items())))
    print('패턴 평균 ' + ' < '.join('%s %s' % (p, format(rnd(sum(v) / len(v)), ','))
                                for p, v in sorted(by_pat.items(),
                                                   key=lambda kv: sum(kv[1]) / len(kv[1]))))
    longs = [c for c in cells.values() if lay_min(c['note']) is not None]
    print('환승 12시간 이상 %d칸 · 20시간 이상 %d칸'
          % (sum(1 for c in longs if 720 <= lay_min(c['note']) < 1200),
             sum(1 for c in longs if lay_min(c['note']) >= 1200)))
    if args.dump_cells:
        for k in sorted(cells, key=lambda x: (ROUTES.index(x[0]), x[1], x[2])):
            c = cells[k]
            print('%s %s %s %9s | %-14s | via=%-5s alt=%-8s | %s'
                  % (k[0], k[1], k[2], format(c['price'], ','), c['airline'] or '-',
                     c['via'], format(c['alt'], ',') if c['alt'] else '-', c['note']))
    if args.dump_cells:
        print('(파일을 쓰지 않았습니다)')
        return 0
    return merge(cells, args)


def recount(fl):
    all_deals = [d for r in fl['routes'] for d in r['deals']]
    by_month = collections.Counter(d['date'][:7] for d in all_deals)
    fl['counts'] = {
        'total': len(all_deals),
        'byMonth': {k: by_month.get(k, 0) for k in fl['months']},
        'holiday': sum(1 for d in all_deals if d['date'] in HOLIDAY_DATES),
        'daytrip': sum(1 for d in all_deals
                       if d['pattern'].split('~')[0] == d['pattern'].split('~')[-1]),
    }
    return fl['counts']


def span(d):
    return '%d/%d~%d' % (int(d['date'][5:7]), int(d['date'][8:10]), int(d['back'][8:10]))


def cell_text(d):
    """'타이베이 6/10~13 목~일 262,460원(타이거항공 타이완 직항 2시간 20분)'."""
    return '%s %s %s %s원(%s %s)' % (CITY[d['code']], span(d), d['pattern'],
                                     format(d['price'], ','),
                                     d.get('airline') or '항공사 미확인',
                                     d.get('note') or '')


def month_note(grid, replaced):
    """2027-06 notes 에 덧붙일 이번 병합 문장(plain text)."""
    lo = min(grid, key=lambda d: (d['price'], ROUTES.index(d['code']), d['date']))
    hi = min(grid, key=lambda d: (-d['price'], ROUTES.index(d['code']), d['date']))
    pats = collections.defaultdict(list)
    for d in grid:
        pats[d['pattern']].append(d['price'])
    pat_avg = sorted(((p, rnd(sum(v) / len(v))) for p, v in pats.items()), key=lambda kv: kv[1])
    weeks = collections.defaultdict(list)
    for d in grid:
        dt = datetime.date.fromisoformat(d['date'])
        weeks[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    week_avg = [(WEEK_LABEL[k], rnd(sum(v) / len(v))) for k, v in sorted(weeks.items())]
    direct = sum(1 for d in grid if d.get('via') is False)
    via = sum(1 for d in grid if d.get('via') is True)
    n_alts = sum(1 for d in grid if d.get('alt'))
    allvia = [c for c in ROUTES
              if all(d.get('via') is True for d in grid if d['code'] == c)]
    longs = [d for d in grid if lay_min(d.get('note')) is not None]
    long12 = [d for d in longs if 720 <= lay_min(d['note']) < 1200]
    long20 = [d for d in longs if lay_min(d['note']) >= 1200]
    unknown = [d for d in grid if d.get('via') is None]
    nodirect = [c for c in allvia
                if all(not d.get('alt') for d in grid if d['code'] == c)]
    rep_old = rnd(sum(r[1] for r in replaced) / len(replaced))
    rep_new = rnd(sum(r[2] for r in replaced) / len(replaced))
    ties_lo = sum(1 for d in grid if d['price'] == lo['price'])
    week_gap = abs(week_avg[0][1] - week_avg[1][1])
    text = (
        '2027년 6월 1~2주차(6/3~7 · 6/10~14)는 부산 출발 기존 24개 노선 5패턴 240칸을 전부 '
        '실측했습니다 — 이 두 주 5패턴은 이제 240/240칸 모두 금액이 있습니다. 앱에 \'가격표\' '
        '자리표시(직항/경유 미확인)로만 있던 ' + str(len(replaced)) + '칸은 같은 노선·출발일·패턴의 '
        '실측값으로 교체했고(교체 칸 평균 ' + format(rep_old, ',') + '원 → ' + format(rep_new, ',')
        + '원), 나머지 ' + str(len(grid) - len(replaced)) + '칸을 새로 넣었습니다(추정·보간 없음 · '
        '미오픈 0칸 · 판매편 0건 0칸). 이 격자에 이미 값이 있던 0박 당일치기 4칸'
        '(후쿠오카·오사카 6/6 일~일 · 도쿄 6/4 금~금 · 오키나와 6/5 토~토)은 이번 5패턴 조사 '
        '범위 밖이라 그대로입니다. 240칸 최저는 ' + cell_text(lo)
        + (' (같은 금액 ' + str(ties_lo) + '칸)' if ties_lo > 1 else '')
        + '이고, 최고는 ' + cell_text(hi) + '으로 최저의 ' + ('%.2f' % (hi['price'] / lo['price']))
        + '배입니다. 240칸 평균은 ' + format(rnd(sum(d['price'] for d in grid) / len(grid)), ',')
        + '원이고 주차 평균은 ' + ' · '.join('%s %s원' % (w, format(v, ',')) for w, v in week_avg)
        + '으로 두 주 차이가 ' + format(week_gap, ',') + '원뿐입니다. 패턴 평균은 '
        + ' < '.join('%s %s원' % (p, format(v, ',')) for p, v in pat_avg)
        + ' 순으로, 2박 ' + pat_avg[0][0] + '이 3박 ' + pat_avg[-1][0] + '보다 '
        + format(pat_avg[-1][1] - pat_avg[0][1], ',') + '원 쌉니다. 최저가가 직항인 칸은 '
        + str(direct) + '칸, 경유 ' + str(via) + '칸이고 직항 금액을 함께 적은 칸은 ' + str(n_alts)
        + '칸입니다. '
        + ('·'.join(CITY[c] for c in allvia) + ' ' + str(len(allvia))
           + '개 노선은 이 두 주 10칸의 최저가가 모두 경유이고, 그중 '
           + '·'.join(CITY[c] for c in nodirect) + ' ' + str(len(nodirect))
           + '개 노선은 왕복 논스톱 운임 자체가 표시되지 않았습니다(마카오는 부산 직항편이 없음). '
           if allvia else '')
        + ('칭다오 6/4~6 금~일 1칸은 최저가 탭 금액만 있어 편성을 확인하지 못해 \'직항/경유 미확인\''
           '으로 두었습니다(추정하지 않음). ' if unknown else '')
        + '경유 대기가 긴 칸은 '
        + ' · '.join('%s %s %s' % (CITY[d['code']], span(d),
                                   ('환승 ' + re.search(r'환승 ([^·]+?) ·', d['note']).group(1))
                                   if '환승' in d['note'] else '총 ' + re.search(r'총 ([^ ]+)', d['note']).group(1))
                   for d in sorted(long20 + long12, key=lambda d: -lay_min(d['note']))[:4])
        + '이고, 환승 12시간 이상 20시간 미만이 ' + str(len(long12)) + '칸 · 20시간 이상이 '
        + str(len(long20)) + '칸이라 앱의 경유 12h+ · 20h+ 경고가 붙습니다.')
    return text


def default_note(grid, replaced, before_total, after_total):
    lo = min(grid, key=lambda d: d['price'])
    return ('2026-11-20 KST ⑤ 항공 부산 출발 기존 24개 노선 2027년 6월 1~2주차(6/3~7 · 6/10~14) '
            '5패턴 240칸 완결 — 가격표 자리표시 %d칸 교체 + 빈칸 %d칸 실측, 최저 %s %s %s %s원(%s), '
            '직항이 최저가인 칸 %d, 총 %s→%s건'
            % (len(replaced), len(grid) - len(replaced), CITY[lo['code']], span(lo), lo['pattern'],
               format(lo['price'], ','), lo.get('note') or '',
               sum(1 for d in grid if d.get('via') is False),
               format(before_total, ','), format(after_total, ',')))


def merge(cells, args):
    master = json.load(open(MASTER, encoding='utf-8'))
    fl = master['flights']
    routes = {r['code']: r for r in fl['routes']}
    for code in ROUTES:
        if code not in routes:
            raise SystemExit('노선 %s 가 없습니다' % code)

    frozen = {k: json.dumps(master.get(k), ensure_ascii=False, sort_keys=True)
              for k in ('hotels', 'accor', 'sources', 'window', 'built', 'voucherExpiry',
                        'schema', 'version', 'ttang')}
    patterns_before = json.dumps(fl['patterns'], ensure_ascii=False)
    weeks_before = json.dumps(fl['weeks'], ensure_ascii=False)
    nosale_before = json.dumps(fl['noSale'], ensure_ascii=False)
    notes_before = {k: v for k, v in fl['notes'].items() if k != MONTH}
    deals_before = {c: json.loads(json.dumps(routes[c]['deals'])) for c in ROUTES}
    daytrip_before = {c: json.dumps(routes[c]['daytrip'], ensure_ascii=False) for c in ROUTES}
    other_before = json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                              ensure_ascii=False, sort_keys=True)
    before_total = fl['counts']['total']
    before_jun = fl['counts']['byMonth'][MONTH]
    before_extended = master.get('extended', '')
    before_counts = dict(master['counts'])
    before_nosale_jun = [n for n in fl['noSale'] if n.get('date', '')[:7] == MONTH]

    # 이 격자에 이미 있던 칸 — '가격표' 자리표시(직항/경유 미확인)만 교체 대상이다
    placeholders = {}
    for code in ROUTES:
        for d in routes[code]['deals']:
            if not (GRID_START <= d['date'] <= GRID_END) or d['pattern'] not in PAT_NIGHTS:
                continue          # 0박 당일치기 등 이번 조사 범위 밖은 건드리지 않는다
            if d.get('src') != '가격표' or d.get('note') != '가격표 실측 · 직항/경유 미확인':
                raise SystemExit('이 격자에 예상 밖의 기존 칸: %s %s'
                                 % (code, json.dumps(d, ensure_ascii=False)))
            placeholders[(code, d['date'], d['pattern'])] = d
    if len(placeholders) != EXPECT_PLACEHOLDER:
        raise SystemExit('자리표시 칸 %d개 (기대 %d개): %s'
                         % (len(placeholders), EXPECT_PLACEHOLDER, sorted(placeholders)))
    new_keys = set(cells) - set(placeholders)
    if len(new_keys) != EXPECT_NEW:
        raise SystemExit('새 칸 %d개 (기대 %d개)' % (len(new_keys), EXPECT_NEW))
    print('자리표시 %d칸 교체 · 새 칸 %d칸 추가' % (len(placeholders), len(new_keys)))

    def make(v):
        deal = collections.OrderedDict()
        deal['date'] = v['date']
        deal['back'] = v['back']
        deal['pattern'] = v['pattern']
        deal['price'] = v['price']
        if v['airline']:
            deal['airline'] = v['airline']
        deal['via'] = v['via']
        if v['alt']:
            deal['alt'] = v['alt']
        deal['note'] = v['note']
        return json.loads(json.dumps(deal))

    replaced = []
    for key, old in placeholders.items():
        deals = routes[key[0]]['deals']
        idx = next(i for i, d in enumerate(deals)
                   if (d['date'], d['pattern']) == (key[1], key[2]))
        deals[idx] = make(cells[key])
        replaced.append((key, old['price'], cells[key]['price']))
    added = []
    for key in sorted(new_keys):
        routes[key[0]]['deals'].append(make(cells[key]))
        added.append(key)
    for code in ROUTES:
        routes[code]['deals'].sort(key=lambda d: (d['date'], WD[d['pattern'][0]]))
        have = [(d['date'], d['pattern']) for d in routes[code]['deals']]
        if len(set(have)) != len(have):
            raise SystemExit('%s (출발일·패턴) 중복' % code)
        for d in routes[code]['deals']:
            for word in BANNED:
                if word in json.dumps(d, ensure_ascii=False):
                    raise SystemExit('%s %s 값에 제3자 사이트 이름(%s)이 있습니다'
                                     % (code, d['date'], word))

    counts = recount(fl)
    if counts['total'] != before_total + len(added):
        raise SystemExit('총 %d건 (기대 %d건)' % (counts['total'], before_total + len(added)))
    if counts['byMonth'][MONTH] != before_jun + len(added):
        raise SystemExit('%s %d건 (기대 %d건)' % (MONTH, counts['byMonth'][MONTH],
                                                 before_jun + len(added)))

    # 병합 뒤 격자 240칸 검사
    grid = [dict(d, code=r['code']) for r in fl['routes'] if r['code'] in ROUTES
            for d in r['deals'] if GRID_START <= d['date'] <= GRID_END
            and d['pattern'] in PAT_NIGHTS]
    if len(grid) != EXPECT_GRID:
        raise SystemExit('이 격자 %d칸 (기대 %d칸)' % (len(grid), EXPECT_GRID))
    if [d for d in grid if not d.get('price')]:
        raise SystemExit('금액 없는 칸이 있습니다')
    if [d for d in grid if d.get('src')]:
        raise SystemExit('가격표 자리표시 칸이 남아 있습니다')
    if [d for d in grid if not d.get('note')]:
        raise SystemExit('note 없는 칸이 있습니다')
    ps = [d['price'] for d in grid]
    if (min(ps), max(ps)) != EXPECT_OVERALL:
        raise SystemExit('격자 최저·최고 %s (기대 %s)' % ((min(ps), max(ps)), EXPECT_OVERALL))
    if rnd(sum(ps) / len(ps)) != EXPECT_AVG:
        raise SystemExit('격자 평균 %d (기대 %d)' % (rnd(sum(ps) / len(ps)), EXPECT_AVG))
    for code in ROUTES:
        v = [d['price'] for d in grid if d['code'] == code]
        if len(v) != 10 or (min(v), max(v)) != EXPECT_GRID_ROUTE[code]:
            raise SystemExit('격자 %s %d칸 %s (기대 %s)'
                             % (code, len(v), (min(v), max(v)), EXPECT_GRID_ROUTE[code]))
    unknown = [(d['code'], d['date'], d['pattern']) for d in grid if d.get('via') is None]
    if sorted(unknown) != sorted(EXPECT_UNKNOWN):
        raise SystemExit('편성 미확인 칸 %s (기대 %s)' % (sorted(unknown), sorted(EXPECT_UNKNOWN)))
    n_alt = sum(1 for d in grid if d.get('alt'))
    if n_alt != EXPECT_ALT:
        raise SystemExit('직항 금액 병기 %d칸 (기대 %d칸)' % (n_alt, EXPECT_ALT))
    direct = sum(1 for d in grid if d.get('via') is False)
    if direct != EXPECT_DIRECT:
        raise SystemExit('직항이 최저가인 칸 %d (기대 %d)' % (direct, EXPECT_DIRECT))

    week = collections.defaultdict(list)
    for d in grid:
        dt = datetime.date.fromisoformat(d['date'])
        week[(dt - datetime.timedelta(days=(dt.weekday() - WD['목']) % 7)).isoformat()] \
            .append(d['price'])
    for thu, want in EXPECT_WEEK_AVG.items():
        v = week[thu]
        if rnd(sum(v) / len(v)) != want:
            raise SystemExit('%s 평균 %d (기대 %d)' % (thu, rnd(sum(v) / len(v)), want))
    pat = collections.defaultdict(list)
    for d in grid:
        pat[d['pattern']].append(d['price'])
    for p, want in EXPECT_PAT_AVG.items():
        v = pat[p]
        if len(v) != 48 or rnd(sum(v) / len(v)) != want:
            raise SystemExit('%s %d칸 평균 %d (기대 48칸 %d)'
                             % (p, len(v), rnd(sum(v) / len(v)), want))
    longs = [lay_min(d.get('note')) for d in grid if d.get('via') is True]
    got_long = (sum(1 for x in longs if x is not None and 720 <= x < 1200),
                sum(1 for x in longs if x is not None and x >= 1200))
    if got_long != EXPECT_LONG:
        raise SystemExit('장시간 경유 %s (기대 %s)' % (got_long, EXPECT_LONG))

    # 보존 확인 — 호텔·땡처리·다른 노선·다른 달 문구·noSale 은 값 대조
    for key, old in frozen.items():
        if json.dumps(master.get(key), ensure_ascii=False, sort_keys=True) != old:
            raise SystemExit('%s 가 바뀌었습니다' % key)
    if json.dumps(fl['patterns'], ensure_ascii=False) != patterns_before:
        raise SystemExit('패턴 정의가 바뀌었습니다')
    if json.dumps(fl['weeks'], ensure_ascii=False) != weeks_before:
        raise SystemExit('주차 정의가 바뀌었습니다')
    if json.dumps(fl['noSale'], ensure_ascii=False) != nosale_before:
        raise SystemExit('noSale 이 바뀌었습니다')
    if json.dumps([r for r in fl['routes'] if r['code'] not in ROUTES],
                  ensure_ascii=False, sort_keys=True) != other_before:
        raise SystemExit('다른 노선 데이터가 바뀌었습니다')
    for code in ROUTES:
        old = deals_before[code]
        cur = routes[code]['deals']
        n_new = sum(1 for k in new_keys if k[0] == code)
        n_rep = sum(1 for k in placeholders if k[0] == code)
        if len(cur) != len(old) + n_new:
            raise SystemExit('%s 딜 %d건 (기존 %d + 새 %d)' % (code, len(cur), len(old), n_new))
        have = {(d['date'], d['pattern']): d for d in cur}
        kept = 0
        for o in old:
            if (code, o['date'], o['pattern']) in placeholders:
                continue          # 이번 실측으로 교체된 칸
            got = have.get((o['date'], o['pattern']))
            if got is None:
                raise SystemExit('%s 기존 딜이 사라졌습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
            if json.dumps(got, ensure_ascii=False, sort_keys=True) != \
                    json.dumps(o, ensure_ascii=False, sort_keys=True):
                raise SystemExit('%s 기존 딜이 바뀌었습니다: %s %s'
                                 % (code, o['date'], o['pattern']))
            kept += 1
        if len(old) - n_rep != kept:
            raise SystemExit('%s 보존 칸 계산이 어긋났습니다' % code)
        keys = [(d['date'], WD[d['pattern'][0]]) for d in cur]
        if keys != sorted(keys):
            raise SystemExit('%s 딜 정렬이 깨졌습니다' % code)
        if json.dumps(routes[code]['daytrip'], ensure_ascii=False) != daytrip_before[code]:
            raise SystemExit('%s 당일치기 요약이 바뀌었습니다' % code)
    if {k: v for k, v in fl['notes'].items() if k != MONTH} != notes_before:
        raise SystemExit('다른 달 커버리지 문구가 바뀌었습니다')
    if '**' in json.dumps(fl['notes'], ensure_ascii=False):
        raise SystemExit('월별 notes 에 마크다운 별표가 들어갔습니다')
    for word in BANNED:
        if word in json.dumps(fl['notes'], ensure_ascii=False):
            raise SystemExit('notes 에 제3자 사이트 이름이 들어갔습니다: %s' % word)
    if [n for n in fl['noSale'] if n.get('date', '')[:7] == MONTH] != before_nosale_jun:
        raise SystemExit('2027-06 noSale 기록이 바뀌었습니다')

    month_sent = month_note(grid, replaced)
    if '**' in month_sent:
        raise SystemExit('notes 문장에 마크다운 별표가 있습니다')
    for word in BANNED:
        if word in month_sent:
            raise SystemExit('notes 문장에 제3자 사이트 이름(%s)이 있습니다' % word)
    fl['notes'][MONTH] = fl['notes'][MONTH].rstrip() + ' ' + month_sent

    master['counts'] = dict(before_counts)
    master['counts']['deals'] = counts['total']
    note = args.note or default_note(grid, replaced, before_total, counts['total'])
    master['extended'] = (before_extended + ' / ' + note).strip(' /')

    print('교체 %d칸(평균 %s원 → %s원) · 새 칸 %d칸'
          % (len(replaced),
             format(rnd(sum(r[1] for r in replaced) / len(replaced)), ','),
             format(rnd(sum(r[2] for r in replaced) / len(replaced)), ','),
             len(added)))
    print('총 %d → %d건 (주말형 %d · 당일치기 %d)'
          % (before_total, counts['total'], counts['total'] - counts['daytrip'],
             counts['daytrip']))
    print('2027-06 %d → %d건' % (before_jun, counts['byMonth'][MONTH]))
    print('notes[2027-06] 새 문장:', month_sent)
    print('extended 추가:', note)

    if args.dry_run:
        print('(dry-run — 파일을 쓰지 않았습니다)')
        return 0
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('저장: %s' % MASTER)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
