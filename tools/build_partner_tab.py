#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑧ 외항사 마일 — 부산(PUS)·인천(ICN) 출발 보너스 좌석 탭.

자료: tools/partner_tab/raw/{슬러그}_dep_{PUS|ICN}*.txt (브라우저로 직접 확인한 표를 옮긴 것)
      한 줄 = MM-DD|마지막확인|도착코드|이코|프이|비즈|퍼스트
      등급 값은 "" 또는 "직항편수:마일" (예: 0:9000 = 직항 9,000마일)
출력: data/app/tab9_partner_mileage.json      (부산 PUS — 9개 프로그램)
      data/app/tab9_partner_mileage_icn.json  (인천 ICN — 같은 9개 프로그램)
      index.html 의 NAV·SECTION·CSS·JS 블록과는 한 번만 연결한다.

    python3 tools/build_partner_tab.py            # JSON 두 개 만들고 index.html 연결
    python3 tools/build_partner_tab.py --check    # 넣지 않고 상태만
"""
import datetime
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')
ASSETS = os.path.join(ROOT, 'tools', 'partner_tab')
RAW = os.path.join(ASSETS, 'raw')
APPDIR = os.path.join(ROOT, 'data', 'app')

NAV_START, NAV_END = '<!-- PARTNER:NAV -->', '<!-- /PARTNER:NAV -->'
SEC_START, SEC_END = '<!-- PARTNER:SECTION -->', '<!-- /PARTNER:SECTION -->'
CSS_START, CSS_END = '/* PARTNER:CSS */', '/* /PARTNER:CSS */'
JS_START, JS_END = '// PARTNER:JS', '// /PARTNER:JS'

KEY = 'partner-mileage'

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
}
DOMESTIC = {'GMP', 'CJU', 'PUS', 'TAE', 'KWJ', 'CJJ', 'RSU', 'KUV', 'HIN', 'USN', 'WJU', 'MPC', 'KPO', 'YNY', 'ICN', 'SEL'}

NOTE_PUS = {
    'flyingblue': '',
    'smiles': '',
    'virgin': '',
    'delta': '경유편 다수 포함',
    'united': '부산 출발은 싱가포르(SIN) 노선만 추적',
    'aeroplan': '',
    'asiamiles': '원천에 부산 자료 없음 — 공홈 직접 조회',
    'british': '원천에 부산 자료 없음 — 공홈 직접 조회',
    'jal': '원천에 부산 자료 없음 — 공홈 직접 조회',
}
NOTE_ICN = {
    'flyingblue': '',
    'smiles': '',
    'virgin': '경유편 다수 포함',
    'delta': '경유편 다수 포함',
    'united': '경유편 다수 포함',
    'aeroplan': '경유편 다수 포함',
    'asiamiles': '인천↔홍콩 노선만 추적',
    'british': '원천에 인천 자료 없음 — 공홈 직접 조회',
    'jal': '원천에 인천 자료 없음 — 공홈 직접 조회',
}

# 출발지별 설정 — 창(목표 1년)·수집 구간·안내 문구가 다르다
ORIGINS = [
    dict(code='PUS', name='부산', full='부산/김해(PUS)', file='tab9_partner_mileage.json',
         src='항공사 마일리지 프로그램 9곳 보너스 좌석 실측(부산/김해 PUS)',
         sweep=('2026-11-22', '2027-11-21'), notes=NOTE_PUS,
         dirNote='부산 출발(PUS→) 방향만 수집 — 부산 도착(→PUS) 방향은 다음 수집에서 채웁니다'),
    dict(code='ICN', name='인천', full='인천(ICN)', file='tab9_partner_mileage_icn.json',
         src='항공사 마일리지 프로그램 9곳 보너스 좌석 실측(인천 ICN)',
         sweep=('2026-11-22', '2027-11-21'), notes=NOTE_ICN,
         dirNote='인천 출발(ICN→) 방향만 수집 — 인천 도착(→ICN) 방향은 다음 수집에서 채웁니다'),
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
    for slug, name, short, alliance, alliance_name, url, url_label in PROGRAMS:
        files = sorted(glob.glob(os.path.join(RAW, slug + '_dep_' + cfg['code'] + '*.txt')))
        got = []
        for f in files:
            for rec in parse_raw(f):
                date, seen, dest = full_date(rec[0]), rec[1], rec[2]
                if dest in DOMESTIC:
                    continue              # 국내선은 국제선 화면에서 뺀다
                cab = [norm_cabin(v) for v in rec[3:7]]
                got.append([slug, date, seen, dest, cab[0], cab[1], cab[2], cab[3], 0])
                dests.setdefault(dest, {'code': dest, 'city': CITY.get(dest, dest)})
        programs.append({'key': slug, 'name': name, 'short': short,
                         'alliance': alliance, 'allianceName': alliance_name,
                         'url': url, 'urlLabel': url_label, 'rows': len(got)})
        coverage.append({'name': name, 'key': slug, 'rows': len(got),
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
        'programs': programs,
        'dests': sorted(dests.values(), key=lambda d: d['code']),
        'rows': rows,
        'coverage': coverage,
        'counts': {'rows': len(rows), 'programs': len(counts), 'dests': len(dests),
                   'domesticExcluded': True},
    }


def main(argv):
    check = '--check' in argv
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    built = {}
    for cfg in ORIGINS:
        data = build_origin(cfg, now)
        built[cfg['code']] = data
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

    pus = built['PUS']
    icn = built['ICN']
    src = open(INDEX, encoding='utf-8').read()

    def asset(n):
        with open(os.path.join(ASSETS, n), encoding='utf-8') as fp:
            return fp.read().rstrip('\n')

    def put(text, start, end, body, anchor, before=True):
        if start in text and end in text:
            a = text.index(start)
            b = text.index(end, a) + len(end)
            return text[:a] + start + '\n' + body + '\n' + end + text[b:], 'replaced'
        if anchor not in text:
            raise SystemExit('앵커를 찾지 못했습니다: %r' % anchor[:60])
        i = text.index(anchor)
        block = start + '\n' + body + '\n' + end
        if before:
            return text[:i] + block + '\n' + text[i:], 'inserted'
        j = i + len(anchor)
        return text[:j] + '\n' + block + text[j:], 'inserted'

    NAV_HTML = ('    <button class="tab" data-tab="%s" type="button" aria-label="외항사 마일 — 부산(PUS)·인천(ICN) 출발 9개 프로그램 보너스 좌석">'
                '<span class="t-full">⑧ 외항사 마일</span>'
                '<span class="t-short" aria-hidden="true">⑧ 외항사</span> <b>%d</b></button>'
                % (KEY, pus['counts']['rows']))

    TABS_ENTRY = ("'%s':{title:'⑧ 외항사 마일 — 부산(PUS)·인천(ICN) 9개 프로그램 보너스 좌석',"
                  "sub:'에어프랑스 플라잉블루 · 골 스마일즈 · 버진 애틀랜틱 · 델타 스카이마일즈 · 유나이티드 마일리지플러스 · "
                  "에어캐나다 에어로플랜 · 캐세이 아시아 마일즈 · 영국항공 아비오스 · JAL 마일지뱅크 9곳을 "
                  "출발지(부산 PUS / 인천 ICN)를 골라 1년(365일) 달력 · 이코노미/프리미엄/비즈니스/퍼스트로 나눠 보여 줍니다. "
                  "달력의 날짜 칸을 누르면 그 날의 프로그램별·등급별 필요 마일과 공식 발권 링크가 열리고, "
                  "원천이 열어 준 구간 밖은 미수집으로 표시합니다. 각 행의 예약 버튼은 해당 프로그램의 공식 사이트로 엽니다. "
                  "원천에 좌석 수량·세금·수수료가 없어 표시하지 않습니다. / 예약 전 항공사 공식 사이트에서 재확인',"
                  "checked:'수집 기준: %s · 9개 프로그램 실측 · 부산 %s~%s %s건 · 인천 %s~%s %s건',start:'%s',end:'%s'}"
                  % (KEY, now.strftime('%Y-%m-%d %H:%M KST'),
                     pus['collectedFrom'], pus['collectedTo'], format(pus['counts']['rows'], ','),
                     icn['collectedFrom'], icn['collectedTo'], format(icn['counts']['rows'], ','),
                     (pus['collectedFrom'] or '2026-11')[:7],
                     (pus['dateTo'] or '2027-11')[:7]))

    SHORT_ENTRY = ("'%s':{sub:'9개 프로그램 · 부산(PUS)·인천(ICN) 출발 보너스 좌석',"
                   "checked:'조회 기준: %s KST'}" % (KEY, now.strftime('%Y.%m.%d %H:%M')))

    HOOKS = [
        ('setDealPanels',
         "const cng=document.querySelector('.note-grid');",
         "const pp=document.getElementById('pmPanel');if(pp)pp.hidden=which!=='%s';"
         "const cng=document.querySelector('.note-grid');" % KEY),
        ('render() 디스패치',
         "if(st.tab==='mileage'){renderMileage();hashSync();return}",
         "if(st.tab==='mileage'){renderMileage();hashSync();return}\n"
         "  if(st.tab==='%s'){renderPartner();hashSync();return}" % KEY),
        ('DATA_READY', "mileage:false};", "mileage:false,'%s':false};" % KEY),
        ('PART_FILE', "mileage:'tab8_mileage.json'},",
         "mileage:'tab8_mileage.json','%s':'tab9_partner_mileage.json'}," % KEY),
    ]

    before = len(src)
    src, s_nav = put(src, NAV_START, NAV_END, NAV_HTML, '<!-- /MILEAGE:NAV -->', False)
    src, s_sec = put(src, SEC_START, SEC_END, asset('section.html'), '  <section id="valetPanel"')
    src, s_css = put(src, CSS_START, CSS_END, asset('tab.css'), '/* ── 반응형 ─')
    src, s_js = put(src, JS_START, JS_END, asset('app.js'), 'function activate(tab){')

    if "'%s':{title:'⑧" % KEY not in src:
        anchor = 'valet:{title:'
        if anchor not in src:
            raise SystemExit('const tabs 의 valet 항목을 찾지 못했습니다')
        i = src.index(anchor)
        src = src[:i] + TABS_ENTRY + ',' + src[i:]
        s_tabs = 'inserted'
    else:
        # 이미 있으면 제목·설명·기준 문구를 이번 빌드 값으로 맞춘다(디자인 v2 이후 이름·문구 통일)
        src, n1 = re.subn(r"'%s':\{title:'.*?\},valet:" % KEY, TABS_ENTRY + ",valet:", src,
                          count=1, flags=re.S)
        s_tabs = 'updated' if n1 else 'already'
    src, n2 = re.subn(r"'%s':\{sub:'[^']*',checked:'[^']*'\}" % KEY, SHORT_ENTRY, src, count=1)
    s_short = 'updated' if n2 else 'already'

    hooks = []
    # 캐시 키(DATA_BUST)는 반드시 이번 빌드 값으로 올린다 — 이미 ⑧ 키가 있어도 값을 갱신한다
    src, nb = re.subn(r"'%s':'[^']*'" % KEY, "'%s':'2026-11-22h'" % KEY, src, count=1)
    hooks.append(('DATA_BUST', 'updated' if nb else 'missing'))
    # 자료 로더 — ⑧ 가지가 없을 때만 붙인다(있으면 그대로 둔다)
    if "else if(tab==='%s'){" % KEY not in src:
        old = "    }else if(tab==='mileage'){\n      Object.assign(MGD,data);mgPrep();\n      if(st.tab==='mileage')renderMileage();\n    }"
        new = old + ("\n    }else if(tab==='%s'){\n      Object.assign(PMD,data);pmPrep();\n"
                     "      if(st.tab==='%s')renderPartner();\n    }" % (KEY, KEY))
        if old not in src:
            raise SystemExit('연결 고리를 찾지 못했습니다: loadPart')
        src = src.replace(old, new, 1)
        hooks.append(('loadPart', 'patched'))
    else:
        hooks.append(('loadPart', 'already'))

    for name, old, new in HOOKS:
        if new in src:
            hooks.append((name, 'already'))
            continue
        # 다른 탭의 캐시 키가 올라가 old 문자열이 사라져도, ⑧ 키가 이미 있으면 이미 연결된 것이다
        if name == 'PART_FILE' and "'%s':" % KEY in src:
            hooks.append((name, 'already'))
            continue
        if old not in src:
            raise SystemExit('연결 고리를 찾지 못했습니다: %s\n  %r' % (name, old[:100]))
        src = src.replace(old, new, 1)
        hooks.append((name, 'patched'))

    print('nav     %s\nsection %s\ncss     %s\njs      %s\ntabs    %s\nshort   %s'
          % (s_nav, s_sec, s_css, s_js, s_tabs, s_short))
    for n, s in hooks:
        print('hook    %-16s %s' % (n, s))
    print('index.html %d → %d bytes' % (before, len(src)))
    if check:
        print('(--check: 쓰지 않았습니다)')
        return 0
    with open(INDEX, 'w', encoding='utf-8') as fp:
        fp.write(src)
    print('index.html 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
