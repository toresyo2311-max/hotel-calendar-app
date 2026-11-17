#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""중국·홍콩·마카오 메리어트(리츠칼튼·세인트레지스·W) 40곳 → data/master_db.json 병합.

원본: /workspace/data-sources/marriott-china/*.md (8개 파일, 2026-11-17 조사)
사용법 (저장소 루트에서):
    python3 tools/import_marriott.py --dry     # 파싱 결과·검증만 출력
    python3 tools/import_marriott.py           # master_db.json 에 tab:"marriott" 40곳 반영
    python3 tools/import_marriott.py --json out.json   # 호텔 배열만 파일로 저장

보완본 우선 규칙:
  - W 상하이 더번드·마카오: `6-...W호텔-part2.md` (무료취소 ON 재조회본) 우선
  - 세인트레지스 마카오·라싸, 리츠칼튼 상하이 푸동·포트만·베이징 파이낸셜스트리트:
    `7-...보완1.md` 완성본 우선
"""
import argparse
import datetime
import json
import os
import re
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = '/workspace/data-sources/marriott-china'
MASTER = os.path.join(ROOT, 'data', 'master_db.json')

WINDOW_START = datetime.date(2026, 12, 1)
WINDOW_END = datetime.date(2027, 11, 30)
DAYS = [(WINDOW_START + datetime.timedelta(days=i)).isoformat()
        for i in range((WINDOW_END - WINDOW_START).days + 1)]

F0 = '0-2026-12_2027-11-중국홍콩마카오-리츠칼튼-part1.md'
F1 = '1-2026-12_2027-11-중국홍콩마카오-리츠칼튼-part1b.md'
F2 = '2-2026-12_2027-11-중국홍콩마카오-리츠칼튼-part2.md'
F3 = '3-2026-12_2027-11-중국홍콩마카오-리츠칼튼-part3.md'
F4 = '4-2026-12_2027-11-중국홍콩마카오-세인트레지스.md'
F5 = '5-2026-12_2027-11-중국홍콩마카오-W호텔.md'
F6 = '6-2026-12_2027-11-중국홍콩마카오-W호텔-part2.md'
F7 = '7-2026-12_2027-11-중국-보완1.md'

CASH_SRC = '검색 호텔 1박 총액(세금·수수료 포함·무료취소 ON) · 2026-11-17 조회'

# (id, brand, city, 한국어 이름, 영문명, 파일, 섹션 제목 정규식, 특이사항, 비고)
SPEC = [
    # ── 리츠칼튼 18곳 ─────────────────────────────────────────────
    ('m01', '리츠칼튼', '베이징', '리츠칼튼 베이징 차이나센트럴',
     'The Ritz-Carlton, Beijing (China Central Place)', F0,
     r'^## The Ritz-Carlton, Beijing \(China Central Place\)',
     '2027-10-12 이후 달력 예약창 미오픈(NA) — 매진 아님', None),
    ('m02', '리츠칼튼', '베이징', '리츠칼튼 베이징 파이낸셜스트리트',
     'The Ritz-Carlton Beijing, Financial Street', F7,
     r'^## 리츠칼튼 베이징 파이낸셜스트리트',
     '보완1 완성본(365일) 적용 — part1의 2027-08~11 미조회 구간 채움', None),
    ('m03', '리츠칼튼', '상하이', '리츠칼튼 상하이 푸동',
     'The Ritz-Carlton Shanghai, Pudong', F7,
     r'^## 리츠칼튼 상하이 푸동',
     '보완1 완성본 적용 — 2026-12-31 1,200,000원(연중 최고)', None),
    ('m04', '리츠칼튼', '상하이', '포트만 리츠칼튼 상하이',
     'The Portman Ritz-Carlton, Shanghai', F7,
     r'^## 포트만 리츠칼튼 상하이',
     '보완1 완성본 적용 — 상하이 3곳 중 최저가대(23.8만~38.8만)', None),
    ('m05', '리츠칼튼', '광저우', '리츠칼튼 광저우',
     'The Ritz-Carlton, Guangzhou', F1,
     r'^## The Ritz-Carlton, Guangzhou',
     '원 단위 정확값(1박 요금 API yY52ce) — 2027-10-12~11-30 NA', None),
    ('m06', '리츠칼튼', '선전', '리츠칼튼 선전',
     'The Ritz-Carlton, Shenzhen', F1,
     r'^## The Ritz-Carlton, Shenzhen',
     '원 단위 정확값(1박 요금 API yY52ce) — 2027-10-12~11-30 NA', None),
    ('m07', '리츠칼튼', '청두', '리츠칼튼 청두',
     'The Ritz-Carlton, Chengdu', F2,
     r'^## The Ritz-Carlton, Chengdu \(청두\)',
     '2027-10-11 이후 NA', 'points'),
    ('m08', '리츠칼튼', '시안', '리츠칼튼 시안',
     'The Ritz-Carlton, Xi\'an', F2,
     r'^## The Ritz-Carlton, Xi\'an \(시안\)',
     '2027-10-10 이후 NA', 'points'),
    ('m09', '리츠칼튼', '톈진', '리츠칼튼 톈진',
     'The Ritz-Carlton, Tianjin', F2,
     r'^## The Ritz-Carlton, Tianjin \(톈진\)',
     '2027-10-11 이후 NA', 'points'),
    ('m10', '리츠칼튼', '하이커우', '리츠칼튼 하이커우',
     'The Ritz-Carlton, Haikou', F2,
     r'^## The Ritz-Carlton, Haikou \(하이커우\)',
     '현금 요금 전 구간 NA — 검색 호텔에 지점 미등재(2026-11-17). 실제 요금은 메리어트 공홈·OTA 확인 필요', 'points'),
    ('m11', '리츠칼튼', '싼야', '리츠칼튼 싼야 야롱베이',
     'The Ritz-Carlton Sanya, Yalong Bay', F2,
     r'^## The Ritz-Carlton Sanya, Yalong Bay \(싼야 야롱베이\)',
     '2027-10-12 이후 NA · 6~10월은 1박 128만원 단일가만 노출(하한선)', 'points'),
    ('m12', '리츠칼튼', '하얼빈', '리츠칼튼 하얼빈',
     'The Ritz-Carlton, Harbin', F2,
     r'^## The Ritz-Carlton, Harbin \(하얼빈\)',
     '2027-10-10 이후 NA · 값 있는 날 201일', 'points'),
    ('m13', '리츠칼튼', '난징', '리츠칼튼 난징',
     'The Ritz-Carlton, Nanjing', F3,
     r'^## The Ritz-Carlton, Nanjing \(난징\)',
     '원 단위 정확값 — 2027-05~11 대부분 NA(값 있는 날 186일)', None),
    ('m14', '리츠칼튼', '쑤저우', '리츠칼튼 쑤저우',
     'The Ritz-Carlton, Suzhou', F3,
     r'^## The Ritz-Carlton, Suzhou \(쑤저우\)',
     '2025년 개장 · 원 단위 정확값', None),
    ('m15', '리츠칼튼', '우한', '리츠칼튼 우한',
     'The Ritz-Carlton, Wuhan', F3,
     r'^## The Ritz-Carlton, Wuhan \(우한\)',
     '2026-03 개장 · 4월 중순~7월 NA(값 있는 날 204일)', None),
    ('m16', '리츠칼튼', '홍콩', '리츠칼튼 홍콩',
     'The Ritz-Carlton, Hong Kong', F3,
     r'^## The Ritz-Carlton, Hong Kong \(홍콩\)',
     '원 단위 정확값 · 2026-12-31 2,591,126원(연중 최고)', None),
    ('m17', '리츠칼튼', '마카오', '리츠칼튼 마카오',
     'The Ritz-Carlton, Macau', F3,
     r'^## The Ritz-Carlton, Macau \(마카오\)',
     '요금 0건 — 검색 호텔에 1박 요금 미등록, 전 구간 NA(5개 통화 조회에도 0건)', None),
    ('m18', '리츠칼튼', '지우자이거우', '리츠칼튼 리저브 리사이밸리',
     'Rissai Valley, a Ritz-Carlton Reserve', F3,
     r'^## Rissai Valley, a Ritz-Carlton Reserve \(지우자이거우\)',
     '리츠칼튼 리저브(지우자이거우) · 12월 내내 1,807,509원 반복 = 하한선 값', None),
    # ── 세인트레지스 13곳 ─────────────────────────────────────────
    ('m19', '세인트레지스', '베이징', '세인트레지스 베이징',
     'The St. Regis Beijing', F4,
     r'^## 베이징 \(The St\. Regis Beijing\)',
     '무료취소 최저 · 2027-10-10 이후 NA', None),
    ('m20', '세인트레지스', '청두', '세인트레지스 청두',
     'The St. Regis Chengdu', F4,
     r'^## 청두 \(The St. Regis Chengdu\)',
     '무료취소 최저 · 2027-10-11 이후 NA', None),
    ('m21', '세인트레지스', '상하이', '세인트레지스 상하이 온더번드',
     'The St. Regis on the Bund, Shanghai', F4,
     r'^## 상하이 온더번드 \(The St\. Regis on the Bund, Shanghai\)',
     '무료취소 최저 · 2027-10-10 이후 NA · 상하이 최고가대(중앙값 57.3만)', None),
    ('m22', '세인트레지스', '톈진', '세인트레지스 톈진',
     'St. Regis Tianjin', F4,
     r'^## 톈진 \(St\. Regis Tianjin\)',
     '무료취소 최저 · 5월 하순~8월 무료취소 요금 없음(값 있는 날 232일)', None),
    ('m23', '세인트레지스', '창사', '세인트레지스 창사',
     'The St. Regis Changsha', F4,
     r'^## 창사 \(The St. Regis Changsha\)',
     '무료취소 최저 · 2027-05-15 이후 NA(값 있는 날 164일)', None),
    ('m24', '세인트레지스', '싼야', '세인트레지스 싼야 야롱베이 리조트',
     'The St. Regis Sanya Yalong Bay Resort', F4,
     r'^## 싼야 야롱베이 \(The St\. Regis Sanya Yalong Bay Resort\)',
     '무료취소 최저 · 2027-10-12 이후 NA', None),
    ('m25', '세인트레지스', '주하이', '세인트레지스 주하이',
     'The St. Regis Zhuhai', F4,
     r'^## 주하이 \(The St. Regis Zhuhai\)',
     '무료취소 최저 · 2027-09-06 이후 NA(값 있는 날 190일)', None),
    ('m26', '세인트레지스', '칭다오', '세인트레지스 칭다오',
     'The St. Regis Qingdao', F4,
     r'^## 칭다오 \(The St. Regis Qingdao\)',
     '무료취소 최저 · 중앙값 65.4만(연중 변동 큼)', None),
    ('m27', '세인트레지스', '선전', '세인트레지스 선전',
     'The St. Regis Shenzhen', F4,
     r'^## 선전 \(The St. Regis Shenzhen\)',
     '무료취소 최저 · 2027-10-10 이후 NA', None),
    ('m28', '세인트레지스', '선전', '세인트레지스 선전 바오안',
     'The St. Regis Shenzhen Bao\'an', F4,
     r'^## 선전 바오안 \(The St\. Regis Shenzhen Bao\'an\)',
     '무료취소 최저 · 2027-10-10 이후 NA', None),
    ('m29', '세인트레지스', '홍콩', '세인트레지스 홍콩',
     'The St. Regis Hong Kong', F4,
     r'^## 홍콩 \(The St\. Regis Hong Kong\)',
     '무료취소 최저 · 2027-10-12 이후 NA', None),
    ('m30', '세인트레지스', '마카오', '세인트레지스 마카오',
     'The St. Regis Macao', F7,
     r'^## 세인트레지스 마카오',
     '보완1 완성본 적용(값 있는 날 302일) — 2027-02-09 5,100,000원 등 특수일 고가', None),
    ('m31', '세인트레지스', '라싸', '세인트레지스 라싸 리조트',
     'The St. Regis Lhasa Resort', F7,
     r'^## 세인트레지스 라싸 리조트',
     '메리어트 공홈 월별 15일 CNY 실측만 수록(365일 달력 불가) — 12~3월 CNY 822(약 164,200원), 4~10월 CNY 1,221~1,710(약 243,900~341,500원), 2027-11 NA',
     'lhasa'),
    # ── W 9곳 ────────────────────────────────────────────────────
    ('m32', 'W', '상하이', 'W 상하이 더번드',
     'W Shanghai – The Bund', F6,
     r'^### 4\.5 W 상하이 – 더번드',
     'part2 무료취소 ON 재조회본 적용 — 2027-04-10만 580,000→523,000원, 나머지 364일 동일', None),
    ('m33', 'W', '광저우', 'W 광저우',
     'W Guangzhou', F5,
     r'^## W Guangzhou',
     '2027-10-12 이후 NA · 최저 173,000원(2027-02-14)', None),
    ('m34', 'W', '시안', 'W 시안',
     'W Xi\'an', F5,
     r'^## W Xi\'an',
     '2027-10-12 이후 NA', None),
    ('m35', 'W', '청두', 'W 청두',
     'W Chengdu', F5,
     r'^## W Chengdu',
     '2027-10-12 이후 NA · 최저 221,000원대 단일가 반복', None),
    ('m36', 'W', '창사', 'W 창사',
     'W Changsha', F6,
     r'^### 4\.1 W 창사',
     'part2 완성본 적용(365일)', None),
    ('m37', 'W', '쑤저우', 'W 쑤저우',
     'W Suzhou', F6,
     r'^### 4\.2 W 쑤저우',
     'part2 완성본 적용(365일)', None),
    ('m38', 'W', '샤먼', 'W 샤먼',
     'W Xiamen', F6,
     r'^### 4\.3 W 샤먼',
     'part2 완성본 적용 · 2027-04-24 1,690,000원(연중 최고)', None),
    ('m39', 'W', '홍콩', 'W 홍콩',
     'W Hong Kong', F5,
     r'^## W Hong Kong',
     '2027-10-13 이후 NA · 2026-12-31 1,440,000원', None),
    ('m40', 'W', '마카오', 'W 마카오 스튜디오시티',
     'W Macau – Studio City', F6,
     r'^### 4\.4 W 마카오',
     'part2 완성본 적용 · 2026-12-31 1,010,000원', None),
]

_cache = {}


def lines_of(fname):
    if fname not in _cache:
        with open(os.path.join(SRC, fname), encoding='utf-8') as fp:
            _cache[fname] = fp.read().split('\n')
    return _cache[fname]


def section(fname, pat):
    lines = lines_of(fname)
    rx = re.compile(pat)
    start = None
    for i, l in enumerate(lines):
        if rx.match(l):
            start = i
            break
    if start is None:
        raise SystemExit('섹션을 찾지 못함: %s / %s' % (fname, pat))
    level = len(lines[start]) - len(lines[start].lstrip('#'))
    end = len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if s.startswith('#') and (len(s) - len(s.lstrip('#'))) <= level:
            end = j
            break
    return lines[start:end]


def daily_table(sec):
    """섹션 안의 '날짜별 1박 요금' 표 → {date: price|None}, rows, header"""
    hi = None
    for i, l in enumerate(sec):
        if l.startswith('|') and re.match(r'\|\s*날짜\s*\|', l) and (
                '요금' in l or '총액' in l or '가격' in l):
            hi = i
            break
    if hi is None:
        return {}, 0, None
    header = sec[hi]
    out, rows, na, unread = {}, 0, 0, 0
    for l in sec[hi + 1:]:
        if not l.startswith('|'):
            if l.strip() == '':
                continue
            break
        cells = [c.strip() for c in l.strip().strip('|').split('|')]
        if not re.fullmatch(r'20\d\d-\d\d-\d\d', cells[0]):
            continue
        rows += 1
        v = cells[-1].replace('*', '').replace('원', '').replace(',', '').strip()
        if re.fullmatch(r'\d+', v):
            out[cells[0]] = int(v)
        else:
            out[cells[0]] = None
            if '미조회' in v:
                unread += 1
            else:
                na += 1
    return out, rows, {'header': header, 'na': na, 'unread': unread}


def points_table(fname, city_hint):
    """part2의 '메리어트 포인트(숙박권) 요율' 표에서 지점별 월 범위를 뽑는다."""
    lines = lines_of(fname)
    start = None
    for i, l in enumerate(lines):
        if l.startswith('## 참고 — 메리어트 포인트'):
            start = i
            break
    if start is None:
        return {}
    res, cur = {}, None
    for l in lines[start:]:
        if not l.startswith('|'):
            continue
        cells = [c.strip() for c in l.strip().strip('|').split('|')]
        if len(cells) < 5:
            continue
        c0 = cells[0]
        if c0.startswith('The Ritz'):
            cur = c0
            res.setdefault(cur, {})   # 뒤에 또 나오는 「지점별 포인트 요약」 표가 앞 표를 덮지 않게
        elif c0 == '' and cur:
            pass
        else:
            continue
        mo = cells[1]
        if not re.fullmatch(r'20\d\d-\d\d', mo):
            continue
        try:
            res[cur][mo] = [int(cells[2].replace(',', '')), int(cells[3].replace(',', '')),
                            int(cells[4].replace(',', '')), int(cells[5])]
        except (ValueError, IndexError):
            continue
    return res


def points_summary(pts):
    if not pts:
        return None
    pts = {m: v for m, v in pts.items() if '2026-12' <= m <= '2027-11'}
    if not pts:
        return None
    months = sorted(pts)
    lo = min(v[0] for v in pts.values())
    hi = max(v[1] for v in pts.values())
    days = [v[3] for v in pts.values()]
    parts = []
    for m in months:
        v = pts[m]
        parts.append('%s.%s %s~%s' % (m[2:4], m[5:7], format(v[0], ','), format(v[1], ',')))
    return ('Bonvoy 포인트(숙박권) %s~%spt · 월별 최저~최고: %s · 포인트 가능일 %d~%d일/월 '
            '(staywithpoints.com, 2026-11-17)' % (format(lo, ','), format(hi, ','),
                                                    ' · '.join(parts), min(days), max(days)))


def lhasa_rates(sec):
    """라싸: 매월 15일 CNY 실측 → 원화 참고값(1 CNY=199.72)을 그 15일에 넣는다."""
    out = {d: None for d in DAYS}
    rows = 0
    for l in sec:
        if not l.startswith('|'):
            continue
        cells = [c.strip() for c in l.strip().strip('|').split('|')]
        if len(cells) < 4 or not re.fullmatch(r'20\d\d-\d\d', cells[0]):
            continue
        d = cells[1]
        krw = re.sub(r'[^\d]', '', cells[3])
        if re.fullmatch(r'20\d\d-\d\d-\d\d', d) and krw:
            out[d] = int(krw)
            rows += 1
    return out, rows


def build():
    pts_all = points_table(F2, '')
    hotels = []
    for hid, brand, city, name, eng, fname, pat, promo, flag in SPEC:
        sec = section(fname, pat)
        if flag == 'lhasa':
            rates, rows = lhasa_rates(sec)
            meta = {'header': '월별 대표(15일)', 'na': 353, 'unread': 0}
            source = ('메리어트 공홈(marriott.com) 예약 화면 · 매월 15일 1박 CNY 실측, '
                      '1 CNY = ₩199.72 환산(2026-11-17) · %s' % fname)
        else:
            rates, rows, meta = daily_table(sec)
            if not rates:
                raise SystemExit('날짜 표 없음: %s' % name)
        missing = [d for d in DAYS if d not in rates]
        filled = {d: rates.get(d) for d in DAYS}
        vals = [v for v in filled.values() if v is not None]
        stat = {
            'rows': rows,
            'values': len(vals),
            'na': len(DAYS) - len(vals),
            'missing_dates': len(missing),
            'min': min(vals) if vals else None,
            'min_date': min(((v, d) for d, v in filled.items() if v is not None),
                            default=(None, None))[1] if vals else None,
            'max': max(vals) if vals else None,
            'median': int(statistics.median(vals)) if vals else None,
        }
        hotel = {
            'id': hid,
            'group': 'marriott',
            'brand': brand,
            'city': city,
            'name': name,
            'english': eng,
            'region': city,
            'promotion': promo,
            'source': source if flag == 'lhasa' else '%s · %s' % (CASH_SRC, fname),
            'rates': filled,
        }
        if flag == 'points':
            # part2의 6곳만 포인트 요율 표가 있다
            key = [k for k in pts_all if k.startswith('The Ritz-Carlton') and (
                name.split()[-1][:2] in k or city in k or
                (city == '싼야' and 'Sanya' in k) or (city == '하얼빈' and 'Harbin' in k) or
                (city == '하이커우' and 'Haikou' in k) or (city == '청두' and 'Chengdu' in k) or
                (city == '시안' and "Xi'an" in k) or (city == '톈진' and 'Tianjin' in k))]
            key = [k for k in key if any(w in k for w in (
                {'청두': 'Chengdu', '시안': "Xi'an", '톈진': 'Tianjin',
                 '하이커우': 'Haikou', '싼야': 'Sanya', '하얼빈': 'Harbin'}[city],))]
            ps = points_summary(pts_all.get(key[0]) if key else None)
            if ps:
                hotel['points'] = {m: v for m, v in pts_all[key[0]].items()
                                   if '2026-12' <= m <= '2027-11'}
                hotel['note'] = ps
        hotels.append((hotel, stat, fname, meta))
    return hotels


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--json')
    a = ap.parse_args(argv)
    built = build()
    print('%-4s %-10s %-9s %-30s %5s %5s %5s %6s %9s %9s %10s' % (
        'id', '브랜드', '도시', '호텔', 'rows', '값', 'NA', '누락', '최저', '최고', '중앙값'))
    bad = 0
    for h, st, fname, meta in built:
        flag = ''
        if st['rows'] != 365 and not h['id'] == 'm31':
            flag = ' ROWS!'
        if st['missing_dates']:
            flag += ' MISSING!'
            bad += 1
        print('%-4s %-10s %-9s %-30s %5d %5d %5d %6d %9s %9s %10s%s' % (
            h['id'], h['brand'], h['city'], h['name'], st['rows'], st['values'], st['na'],
            st['missing_dates'],
            format(st['min'], ',') if st['min'] else '-',
            format(st['max'], ',') if st['max'] else '-',
            format(st['median'], ',') if st['median'] else '-', flag))
    from collections import Counter
    c = Counter(h['brand'] for h, *_ in built)
    print('\n합계 %d곳 · %s' % (len(built), dict(c)))
    print('도시 %d개' % len({h['city'] for h, *_ in built}))
    if bad:
        print('!! 날짜 누락 호텔 %d곳' % bad)
    if a.json:
        with open(a.json, 'w', encoding='utf-8') as fp:
            json.dump([h for h, *_ in built], fp, ensure_ascii=False, indent=1)
        print('wrote', a.json)
    if a.dry:
        return 0
    # master_db.json 병합
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import master_db  # noqa: E402  (같은 도구 폴더의 검증·통계 함수 재사용)

    master = json.load(open(MASTER, encoding='utf-8'))
    keep = [h for h in master['hotels'] if h.get('group') != 'marriott']
    master['hotels'] = keep + [h for h, *_ in built]
    srcs = [s for s in master.get('sources', []) if not s.startswith('marriott-china/')]
    master['sources'] = srcs + ['marriott-china/' + f for f in (
        F0, F1, F2, F3, F4, F5, F6, F7)]
    st = master_db.stats_of(master, master['flights'])
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                          'stayplus', 'routes', 'deals')}
    print('counts', master['counts'])
    master['built'] = '2026-11-17'
    if '메리어트' not in (master.get('extended') or ''):
        master['extended'] = (master.get('extended') or '') + \
            ' / 2026-11-17 14:10 KST ⑤ 메리어트(중국·홍콩·마카오 40곳) 수집 반영'
    txt = json.dumps(master, ensure_ascii=False, indent=1) + '\n'
    with open(MASTER, 'w', encoding='utf-8') as fp:
        fp.write(txt)
    print('master_db.json 갱신 — 호텔 %d곳' % len(master['hotels']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
