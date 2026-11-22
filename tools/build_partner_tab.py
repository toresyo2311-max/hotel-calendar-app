#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑧ 외항사 마일리지(부산) 탭 — 원천 실측 파일을 JSON 으로 만들고 index.html 에 연결한다.

자료: tools/partner_tab/raw/*.txt (브라우저로 직접 확인한 표를 옮긴 것)
      한 줄 = MM-DD|마지막확인|도착코드|이코|프이|비즈|퍼스트
      등급 값은 "" 또는 "직항편수:마일" (예: 0:9000 = 직항 9,000마일)
출력: data/app/tab9_partner_mileage.json  (9개 프로그램 · 부산 출발/도착)

    python3 tools/build_partner_tab.py            # JSON 만들고 index.html 연결
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
OUT = os.path.join(ROOT, 'data', 'app', 'tab9_partner_mileage.json')

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
}
DOMESTIC = {'GMP', 'CJU'}

NOTE_BY_PROG = {
    'flyingblue': '',
    'smiles': '',
    'virgin': '',
    'delta': '경유편 다수 포함',
    'united': '부산 자료 4건뿐',
    'aeroplan': '',
    'asiamiles': '원천에 부산 자료 없음 — 공홈 직접 조회',
    'british': '원천에 부산 자료 없음 — 공홈 직접 조회',
    'jal': '원천에 부산 자료 없음 — 공홈 직접 조회',
}


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


def full_date(mmdd):
    mm, dd = mmdd.split('-')
    year = 2026 if int(mm) >= 11 else 2027
    return '%d-%s-%s' % (year, mm, dd)


def main(argv):
    check = '--check' in argv
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    programs, dests, rows, coverage = [], {}, [], []

    for slug, name, short, alliance, alliance_name, url, url_label in PROGRAMS:
        files = sorted(glob.glob(os.path.join(RAW, slug + '_dep_PUS*.txt')))
        got = []
        for f in files:
            for rec in parse_raw(f):
                date, seen, dest = full_date(rec[0]), rec[1], rec[2]
                if dest in DOMESTIC:
                    continue                      # 국내선(김포·제주)은 국제선 화면에서 뺀다
                cab = [norm_cabin(v) for v in rec[3:7]]
                got.append([slug, date, seen, dest, cab[0], cab[1], cab[2], cab[3], 0])
                dests.setdefault(dest, {'code': dest, 'city': CITY.get(dest, dest)})
        programs.append({'key': slug, 'name': name, 'short': short,
                         'alliance': alliance, 'allianceName': alliance_name,
                         'url': url, 'urlLabel': url_label, 'rows': len(got)})
        coverage.append({'name': name, 'key': slug, 'rows': len(got),
                         'note': NOTE_BY_PROG.get(slug, '')})
        rows.extend(got)

    rows.sort(key=lambda r: (r[8], r[1], r[0], r[3]))
    counts = {}
    for r in rows:
        counts[r[0]] = counts.get(r[0], 0) + 1

    data = {
        'schema': 'partner-mileage/1',
        'observedAt': now.strftime('%Y-%m-%d %H:%M KST'),
        'observedLabel': now.strftime('%Y-%m-%d %H:%M KST'),
        'collectedAt': now.isoformat(timespec='seconds'),
        'sourceLabel': '항공사 마일리지 프로그램 9곳 보너스 좌석 실측(부산/김해 PUS)',
        'windowDays': 60,
        'dateFrom': min(r[1] for r in rows) if rows else '',
        'dateTo': '2027-01-21',
        'dirNote': '부산 출발(PUS→) 방향만 수집 — 부산 도착(→PUS)은 다음 수집에서 채웁니다',
        'programs': programs,
        'dests': sorted(dests.values(), key=lambda d: d['code']),
        'rows': rows,
        'coverage': coverage,
        'counts': {'rows': len(rows), 'programs': len(counts), 'dests': len(dests),
                   'domesticExcluded': True},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))
    print('data/app/tab9_partner_mileage.json  %d건 · %d프로그램 · %d도시'
          % (len(rows), len(counts), len(dests)))
    for c in coverage:
        print('  %-28s %4d %s' % (c['name'], c['rows'], c['note']))

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

    NAV_HTML = ('    <button class="tab" data-tab="%s" type="button" aria-label="외항사 마일리지 부산 — 9개 프로그램 보너스 좌석">'
                '<span class="t-full">⑧ 외항사 마일리지(부산)</span>'
                '<span class="t-short" aria-hidden="true">⑧ 외항사</span> <b>%d</b></button>' % (KEY, len(rows)))

    TABS_ENTRY = ("'%s':{title:'⑧ 외항사 마일리지(부산) — 9개 프로그램 부산 보너스 좌석',"
                  "sub:'에어프랑스 플라잉블루 · 골 스마일즈 · 버진 애틀랜틱 · 델타 스카이마일즈 · 유나이티드 마일리지플러스 · "
                  "에어캐나다 에어로플랜 · 캐세이 아시아 마일즈 · 영국항공 아비오스 · JAL 마일지뱅크 9곳을 "
                  "부산/김해(PUS) 출발·도착 · 앞으로 60일 · 이코노미/프리미엄/비즈니스/퍼스트로 나눠 보여 줍니다. "
                  "도시별 최저 마일과 날짜별 목록을 함께 두고, 각 행의 예약 버튼은 해당 프로그램의 공식 사이트로 엽니다. "
                  "원천에 좌석 수량·세금·수수료가 없어 표시하지 않습니다. / 예약 전 항공사 공식 사이트에서 재확인',"
                  "checked:'수집 기준: %s · 9개 프로그램 실측(부산 출발 방향)',start:'2026-11',end:'2027-01'}"
                  % (KEY, now.strftime('%Y-%m-%d %H:%M KST')))

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
        ('DATA_BUST', "mileage:'2026-11-22b'};", "mileage:'2026-11-22b','%s':'2026-11-22a'};" % KEY),
        ('PART_FILE', "mileage:'tab8_mileage.json'};",
         "mileage:'tab8_mileage.json','%s':'tab9_partner_mileage.json'};" % KEY),
        ('loadPart',
         "    }else if(tab==='mileage'){\n      Object.assign(MGD,data);mgPrep();\n      if(st.tab==='mileage')renderMileage();\n    }",
         "    }else if(tab==='mileage'){\n      Object.assign(MGD,data);mgPrep();\n      if(st.tab==='mileage')renderMileage();\n"
         "    }else if(tab==='%s'){\n      Object.assign(PMD,data);pmPrep();\n      if(st.tab==='%s')renderPartner();\n    }" % (KEY, KEY)),
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
        s_tabs = 'already'

    hooks = []
    for name, old, new in HOOKS:
        if new in src:
            hooks.append((name, 'already'))
            continue
        if old not in src:
            raise SystemExit('연결 고리를 찾지 못했습니다: %s\n  %r' % (name, old[:100]))
        src = src.replace(old, new, 1)
        hooks.append((name, 'patched'))

    print('nav     %s\nsection %s\ncss     %s\njs      %s\ntabs    %s'
          % (s_nav, s_sec, s_css, s_js, s_tabs))
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
