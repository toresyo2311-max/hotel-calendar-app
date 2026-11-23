#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""외항사 9개 프로그램 보너스 좌석 — 부산(PUS)·인천(ICN) 자료 재생성.

자료: tools/partner_tab/raw/{슬러그}_dep_{PUS|ICN}*.txt (브라우저로 직접 확인한 표를 옮긴 것)
      한 줄 = MM-DD|마지막확인|도착코드|이코|프이|비즈|퍼스트
      등급 값은 "" 또는 "직항편수:마일" (예: 0:9000 = 직항 9,000마일)
출력: data/app/tab9_partner_mileage.json      (부산 PUS — 9개 프로그램)
      data/app/tab9_partner_mileage_icn.json  (인천 ICN — 같은 9개 프로그램)
      그리고 ⑧ 마일리지발권 탭 블록(tools/mileage_tab/*)을 index.html 에 다시 채운다.

2026-11-22 통합 이후 ⑨ 외항사 마일 탭은 따로 두지 않는다 — 대한항공(스카이패스)과
한 탭(⑧ 마일리지발권)에서 같은 달력·같은 날짜 시트로 본다. 그래서 이 빌더는 JSON 만
다시 만들고, 화면 블록은 tools/build_mileage_tab.py 에 맡긴다(아래 main 참고).

    python3 tools/build_partner_tab.py             # JSON 두 개 + ⑧ 탭 블록 재생성
    python3 tools/build_partner_tab.py --check     # 쓰지 않고 상태만
    python3 tools/build_partner_tab.py --json-only # JSON 두 개만(화면 블록은 그대로)

주의: 화면 블록(tools/mileage_tab/*)은 2026-11-22 통합 이후 index.html 에 직접 덧붙인
💎 마일리지 가치·구매가 비교표(mlv) 를 아직 담고 있지 않다. 그 상태에서 블록을 다시 채우면
비교표가 지워지므로, 일일 자료 갱신은 --json-only 로 JSON 만 다시 만들고 화면은 건드리지 않는다.
"""
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'tools', 'partner_tab')
RAW = os.path.join(ASSETS, 'raw')
APPDIR = os.path.join(ROOT, 'data', 'app')

PROGRAMS = [
    # key, 슬러그(원자료 파일 접두), 표시 이름, 짧은 이름, 동맹, 동맹 이름, 공식 예약 주소
    ('flyingblue', '에어프랑스·KLM 플라잉 블루', '에어프랑스', 'skyteam', '스카이팀',
     'https://www.flyingblue.com/', '플라잉 블루 공식'),
    ('smiles', 'GOL 스마일즈', '골 스마일즈', 'none', '얼라이언스 없음',
     'https://www.smiles.com.br/', 'Smiles 공식'),
    ('virgin', '버진 애틀랜틱', '버진', 'skyteam', '스카이팀',
     'https://www.virginatlantic.com/', '버진 공식'),
    ('delta', '델타 스카이마일즈', '델타', 'skyteam', '스카이팀',
     'https://www.delta.com/', '델타 공식'),
    ('united', '유나이티드 마일리지플러스', '유나이티드', 'star', '스타얼라이언스',
     'https://www.united.com/', '유나이티드 공식'),
    ('aeroplan', '에어캐나다 에어로플랜', '에어로플랜', 'star', '스타얼라이언스',
     'https://www.aircanada.com/', '에어캐나다 공식'),
    ('asiamiles', '캐세이퍼시픽 아시아 마일즈', '아시아마일즈', 'oneworld', '원월드',
     'https://www.cathaypacific.com/', '캐세이 공식'),
    ('british', '영국항공 아비오스', 'BA 아비오스', 'oneworld', '원월드',
     'https://www.britishairways.com/', '영국항공 공식'),
    ('jal', 'JAL 마일지뱅크', 'JAL', 'oneworld', '원월드',
     'https://www.jal.co.jp/', 'JAL 공식'),
]

CITY = {
    'NRT': '도쿄/나리타', 'HND': '도쿄/하네다', 'KIX': '오사카', 'NGO': '나고야',
    'FUK': '후쿠오카', 'CTS': '삿포로', 'TPE': '타이베이', 'TSA': '타이베이/송산',
    'PVG': '상하이/푸둥', 'SHA': '상하이/훙차오', 'PEK': '베이징', 'CAN': '광저우',
    'DLC': '다롄', 'TSN': '톈진', 'HKG': '홍콩', 'BKK': '방콕', 'DAD': '다낭',
    'CXR': '나트랑', 'HAN': '하노이', 'SGN': '호찌민', 'SIN': '싱가포르',
    'KUL': '쿠알라룸푸르', 'MNL': '마닐라', 'GUM': '괌', 'DEL': '델리',
    'BLR': '벵갈루루', 'CGK': '자카르타', 'NBO': '나이로비',
    # 인천 노선에서 새로 나온 도시
    'YNT': '옌타이', 'TAO': '칭다오', 'SHE': '선양', 'NKG': '난징', 'WUH': '우한',
    'HGH': '항저우', 'CTU': '청두', 'CKG': '충칭', 'XIY': '시안', 'XMN': '샤먼',
    'HFE': '허페이', 'CGO': '정저우', 'HRB': '하얼빈', 'DLC': '다롄',
    'KHH': '가오슝', 'MFM': '마카오', 'VTE': '비엔티안', 'PNH': '프놈펜',
    'RGN': '양곤', 'DPS': '발리', 'SUB': '수라바야', 'CEB': '세부', 'CRK': '클라크',
    'VVO': '블라디보스토크', 'IKA': '테헤란', 'TAS': '타슈켄트', 'ALA': '알마티',
    'AUH': '아부다비', 'DXB': '두바이', 'DOH': '도하', 'IST': '이스탄불',
    'CDG': '파리', 'AMS': '암스테르담', 'FRA': '프랑크푸르트', 'MUC': '뮌헨',
    'LHR': '런던', 'LGW': '런던/개트윅', 'FCO': '로마', 'MXP': '밀라노',
    'BCN': '바르셀로나', 'MAD': '마드리드', 'LIS': '리스본', 'OPO': '포르투',
    'VIE': '빈', 'ZRH': '취리히', 'GVA': '제네바', 'PRG': '프라하', 'BUD': '부다페스트',
    'WAW': '바르샤바', 'CPH': '코펜하겐', 'ARN': '스톡홀름', 'OSL': '오슬로',
    'HEL': '헬싱키', 'DUB': '더블린', 'BRU': '브뤼셀', 'ATH': '아테네',
    'LAX': '로스앤젤레스', 'JFK': '뉴욕', 'EWR': '뉴어크', 'SFO': '샌프란시스코',
    'SEA': '시애틀', 'ORD': '시카고', 'DFW': '댈러스', 'ATL': '애틀랜타',
    'BOS': '보스턴', 'IAD': '워싱턴', 'DEN': '덴버', 'LAS': '라스베이거스',
    'MIA': '마이애미', 'HNL': '호놀룰루', 'YVR': '밴쿠버', 'YYZ': '토론토',
    'YUL': '몬트리올', 'YYC': '캘거리', 'MEX': '멕시코시티', 'SJU': '산후안',
    'GRU': '상파울루', 'EZE': '부에노스아이레스', 'SCL': '산티아고', 'LIM': '리마',
    'BOG': '보고타', 'PTY': '파나마시티', 'SYD': '시드니', 'MEL': '멜버른',
    'BNE': '브리즈번', 'AKL': '오클랜드', 'NAN': '난디', 'GUM': '괌', 'SPN': '사이판',
    'TLV': '텔아비브', 'CAI': '카이로', 'JNB': '요하네스버그', 'NBO': '나이로비',
    'ADD': '아디스아바바', 'MLE': '말레', 'CMB': '콜롬보', 'DEL': '델리',
    # 인천 노선 도시 이름 보강(2026-11-22)
    'PDX': '포틀랜드', 'SLC': '솔트레이크시티', 'SZX': '선전', 'MSP': '미니애폴리스',
    'WUX': '우시', 'FOC': '푸저우', 'DTW': '디트로이트', 'FLL': '포트로더데일',
    'TFU': '청두/톈푸', 'AUS': '오스틴', 'MTY': '몬테레이', 'SBA': '산타바바라',
    'PQC': '푸꾸옥', 'UBN': '울란바토르', 'WNZ': '원저우', 'YNJ': '옌지',
    'CSX': '창사', 'WRO': '브로츠와프', 'RDU': '롤리/더럼', 'OKJ': '오카야마',
    'HKT': '푸껫', 'KIJ': '니가타', 'PHL': '필라델피아', 'SAI': '시엠림',
    'VCE': '베네치아', 'RMQ': '타이중', 'YNZ': '옌청', 'CNX': '치앙마이',
    'KMG': '쿤밍', 'KOJ': '가고시마', 'RUH': '리야드', 'JED': '제다',
    'KTM': '카트만두', 'NGS': '나가사키', 'PKX': '베이징/다싱',
    'AOJ': '아오모리', 'KMJ': '구마모토', 'UKB': '고베', 'OKA': '오키나와',
    'KMQ': '고마쓰', 'OIT': '오이타', 'DYG': '장자제',
    # 귀국편(→PUS · →ICN)에서만 나온 도시
    'SDJ': '센다이',
}
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN', 'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}

# 탐험(Explore) 화면의 노선표에 없어 검색 화면에서 따로 받은 짝.
#   부산↔광저우(CAN) — tools/partner_tab/convert_can_search.py 가 raw/{슬러그}_{dep|arr}_PUS_can.txt 로 넣는다.
SEARCH_ONLY = {'PUS': {'code': 'CAN', 'collected': '2026-11-23'}}

NOTE_PUS = {
    'flyingblue': '',
    'smiles': '',
    'virgin': '',
    'delta': '경유편 다수 포함',
    'united': '부산 쪽은 싱가포르(SIN)·광저우(CAN) 노선만 추적',
    'aeroplan': '',
    'asiamiles': '조회 사이트에 부산 자료 없음 — 공홈 직접 조회',
    'british': '조회 사이트에 부산 자료 없음 — 공홈 직접 조회',
    'jal': '조회 사이트에 부산 자료 없음 — 공홈 직접 조회',
}
NOTE_ICN = {
    'flyingblue': '',
    'smiles': '',
    'virgin': '경유편 다수 포함',
    'delta': '경유편 다수 포함',
    'united': '경유편 다수 포함',
    'aeroplan': '경유편 다수 포함',
    'asiamiles': '인천↔홍콩 노선만 추적',
    'british': '조회 사이트에 인천 자료 없음 — 공홈 직접 조회',
    'jal': '조회 사이트에 인천 자료 없음 — 공홈 직접 조회',
}

# 출발지별 설정 — 창(목표 1년)·수집 구간·안내 문구가 다르다
ORIGINS = [
    dict(code='PUS', name='부산', full='부산/김해(PUS)', file='tab9_partner_mileage.json',
         src='항공사 마일리지 프로그램 9곳 보너스 좌석 실측(부산/김해 PUS)',
         sweep=('2026-11-22', '2027-11-21'), notes=NOTE_PUS,
         dirNote='부산 출발(PUS→) · 부산 도착(→PUS) 두 방향 모두 2026-11-22~2027-11-21 수집'),
    dict(code='ICN', name='인천', full='인천(ICN)', file='tab9_partner_mileage_icn.json',
         src='항공사 마일리지 프로그램 9곳 보너스 좌석 실측(인천 ICN)',
         sweep=('2026-11-22', '2027-11-21'), notes=NOTE_ICN,
         dirNote='인천 출발(ICN→) · 인천 도착(→ICN) 두 방향 모두 2026-11-22~2027-11-21 수집'),
]


def norm_cabin(v):
    """원자료 '0-12000' → '0:12000'(직항편수:마일), 사용 불가 '-' → ''"""
    v = (v or '').strip()
    if not v or v == '-':
        return ''
    m = re.match(r'^(\d+)-(\d+)$', v)
    if not m:
        raise SystemExit('등급 값이 이상합니다: %r' % v)
    return '%s:%s' % (m.group(1), m.group(2))


def parse_raw(path):
    out = []
    with open(path, encoding='utf-8') as fp:
        txt = fp.read()
    for rec in txt.replace('\n', ';').split(';'):
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split('|')
        if len(parts) != 7:
            raise SystemExit('형식이 맞지 않는 줄: %r (%s)' % (rec, os.path.basename(path)))
        out.append(parts)
    return out


def full_date(s):
    if len(s) == 10 and s[4] == '-':
        return s                      # YYYY-MM-DD 전체 날짜는 그대로
    mm, dd = s.split('-')
    year = 2026 if int(mm) >= 11 else 2027
    return '%d-%s-%s' % (year, mm, dd)


def build_origin(cfg, now):
    programs, dests, rows, coverage = [], {}, [], []
    # 방향별 원자료 — 0 = 출발({코드}→, 파일 _dep_), 1 = 도착(→{코드}, 파일 _arr_)
    #   귀국편 파일의 '도시'는 그 편이 떠나는 곳(원자료의 출발 도시)이다. 두 방향 모두
    #   '상대 도시'를 dest 로 두어 화면의 도시 칩·달력이 같은 이름으로 움직인다.
    for slug, name, short, alliance, alliance_name, url, url_label in PROGRAMS:
        got = []
        for d, mid in ((0, '_dep_'), (1, '_arr_')):
            files = sorted(glob.glob(os.path.join(RAW, slug + mid + cfg['code'] + '*.txt')))
            for f in files:
                for rec in parse_raw(f):
                    date, seen, dest = full_date(rec[0]), rec[1], rec[2]
                    if dest in DOMESTIC:
                        continue          # 국내선(김포·제주 ↔ 부산 등)은 국제선 화면에서 뺀다
                    cab = [norm_cabin(v) for v in rec[3:7]]
                    got.append([slug, date, seen, dest, cab[0], cab[1], cab[2], cab[3], d])
                    dests.setdefault(dest, {'code': dest, 'city': CITY.get(dest, dest)})
        n_out = len([r for r in got if r[8] == 0])
        n_in = len(got) - n_out
        programs.append({'key': slug, 'name': name, 'short': short,
                         'alliance': alliance, 'allianceName': alliance_name,
                         'url': url, 'urlLabel': url_label,
                         'rows': len(got), 'rowsOut': n_out, 'rowsIn': n_in})
        coverage.append({'name': name, 'key': slug, 'rows': len(got),
                         'rowsOut': n_out, 'rowsIn': n_in,
                         'note': (cfg['notes'] or {}).get(slug, '')})
        rows.extend(got)

    rows.sort(key=lambda r: (r[8], r[1], r[0], r[3]))
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1

    # 창은 목표 1년(365일). 실제로 수집한 구간은 따로 적어, 달력이 둘을 섞지 않게 한다.
    # → 다음 수집이 뒤 구간까지 닿으면 sweep 끝을 그날까지 올린다.
    SWEEP_FROM, SWEEP_TO = cfg['sweep']
    collected_from = min([r[1] for r in rows] + [SWEEP_FROM]) if rows else SWEEP_FROM
    collected_to = max([r[1] for r in rows] + [SWEEP_TO]) if rows else SWEEP_TO
    d_from = datetime.date.fromisoformat(collected_from)
    d_to = d_from + datetime.timedelta(days=364)
    next_day = (datetime.date.fromisoformat(collected_to) + datetime.timedelta(days=1)).isoformat()

    # 탐험 화면에 없는 짝(광저우)을 검색 화면에서 따로 받았으면 그 사실을 화면에 적는다.
    search_note = ''
    so = SEARCH_ONLY.get(cfg['code'])
    if so:
        can = [r for r in rows if r[3] == so['code']]
        if can:
            c_out = [r for r in can if r[8] == 0]
            c_in = [r for r in can if r[8] == 1]
            cs = min(r[1] for r in can)
            ce = max(r[1] for r in can)
            search_note = (
                '부산↔%s(%s) — 조회 사이트의 탐험 화면에는 이 짝의 노선 줄이 없어, 검색 화면에서 %s에 '
                '±28일 창을 이어 붙여 1년치를 직접 조회했습니다. 출발(PUS→%s) %d줄 · 귀국(%s→PUS) %d줄, '
                '%s~%s 값입니다. 매일 04:00 자동 갱신에는 이 짝이 잡히지 않으므로, 다음 갱신 때 같은 방법으로 '
                '다시 받아야 합니다.'
                % (CITY.get(so['code'], so['code']), so['code'], so['collected'], so['code'],
                   len(c_out), so['code'], len(c_in), cs, ce))

    return {
        'schema': 'partner-mileage/2',
        'origin': {'code': cfg['code'], 'name': cfg['name'], 'full': cfg['full'],
                   'dirNote': cfg['dirNote']},
        'observedAt': now.strftime('%Y-%m-%d %H:%M KST'),
        'observedLabel': now.strftime('%Y-%m-%d %H:%M KST'),
        'collectedAt': now.isoformat(timespec='seconds'),
        'sourceLabel': cfg['src'],
        'windowDays': 365,
        'dateFrom': collected_from,
        'dateTo': d_to.isoformat() if d_to else '',
        'collectedFrom': collected_from,
        'collectedTo': collected_to,
        'collectedDays': (datetime.date.fromisoformat(collected_to) - d_from).days + 1 if rows else 0,
        'windowNote': ('원천은 비로그인 화면에 앞으로 %d일(%s~%s)까지만 열어 줍니다 — 그 뒤 %s~%s는 '
                       '수집하지 못했고 달력에 미수집으로 표시합니다(보간 없음).'
                       % ((datetime.date.fromisoformat(collected_to) - d_from).days + 1,
                          collected_from, collected_to, next_day, d_to.isoformat())) if collected_to < d_to.isoformat() else '',
        'dirNote': cfg['dirNote'],
        'searchNote': search_note,
        'programs': programs,
        'dests': sorted(dests.values(), key=lambda d: d['code']),
        'rows': rows,
        'coverage': coverage,
        'counts': {'rows': len(rows), 'programs': len(counts), 'dests': len(dests),
                   'rowsOut': len([r for r in rows if r[8] == 0]),
                   'rowsIn': len([r for r in rows if r[8] == 1]),
                   'domesticExcluded': True},
    }


def main(argv):
    check = '--check' in argv
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    for cfg in ORIGINS:
        data = build_origin(cfg, now)
        out = os.path.join(APPDIR, cfg['file'])
        if not check:
            os.makedirs(APPDIR, exist_ok=True)
            with open(out, 'w', encoding='utf-8') as fp:
                json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))
        print('%-3s data/app/%-32s %5d건 · %2d프로그램 · %3d도시'
              % (cfg['code'], cfg['file'], data['counts']['rows'],
                 data['counts']['programs'], data['counts']['dests']))
        for c in data['coverage']:
            print('      %-28s %5d %s' % (c['name'], c['rows'], c['note']))

    if '--json-only' in argv:
        print('(--json-only: index.html 화면 블록은 그대로 둡니다)')
        return 0

    # 화면(index.html)은 ⑧ 마일리지발권 탭 하나가 이 자료를 읽는다 —
    # 2026-11-22 통합 이후 ⑨ 외항사 마일 탭은 따로 두지 않는다. 탭 블록은
    # tools/build_mileage_tab.py 가 마커 사이에 다시 채우므로 그 빌더만 부른다.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import build_mileage_tab
    print('── ⑧ 마일리지발권 탭 블록 재생성')
    return build_mileage_tab.main(['--check'] if check else [])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
