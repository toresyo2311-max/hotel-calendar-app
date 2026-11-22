#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑧ 마일리지 + ⑨ 외항사 마일 → ⑧ 마일리지발권 통합 (한 번만 쓰는 이행 스크립트).

index.html 에서 옛 ⑨ 외항사 탭 블록을 걷어내고, 탭 항목·자료 로더·해시 호환·
콤보 탭 자리를 통합 탭에 맞춘다. 화면 본문(NAV·SECTION·CSS·JS)은
tools/build_mileage_tab.py 가 마커 사이에 다시 채운다.

    python3 tools/migrate_mileage_unified.py --check
    python3 tools/migrate_mileage_unified.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, 'index.html')

NAV_HTML = ('    <button class="tab" data-tab="mileage" type="button" '
            'aria-label="마일리지발권 — 대한항공(스카이패스) 부산 14개 노선과 외항사 9개 프로그램 보너스 좌석">'
            '<span class="t-full">⑧ 마일리지발권</span>'
            '<span class="t-short" aria-hidden="true">⑧ 마일발권</span> <b>0</b></button>')

TABS_ENTRY = ("mileage:{title:'⑧ 마일리지발권 — 대한항공 + 외항사 9개 보너스 좌석',"
              "sub:'대한항공(스카이패스)이 공개하는 보너스 좌석(부산 PUS 출발·도착 14개 노선 · 일반석/프레스티지/프레스티지 승급)과 "
              "항공사 마일리지 프로그램 9곳(에어프랑스 플라잉블루 · 골 스마일즈 · 버진 애틀랜틱 · 델타 스카이마일즈 · 유나이티드 마일리지플러스 · "
              "에어캐나다 에어로플랜 · 캐세이 아시아 마일즈 · 영국항공 아비오스 · JAL 마일지뱅크)을 한 12개월 달력에서 봅니다. "
              "달력의 날짜 칸을 누르면 그 날 도시별로 대한항공과 외항사 9개 프로그램의 필요 마일이 같은 시트에 나란히 열려 같은 날·같은 노선을 바로 견줍니다. "
              "출발지는 부산(PUS)·인천(ICN), 방향은 출발·도착을 고를 수 있고(대한항공은 부산 전용), 🧮 마일리지 계산기는 프로그램마다 보유 마일·1마일 참고 가치를 따로 기억합니다. "
              "조회 사이트가 열어 준 구간 밖은 미수집으로 표시합니다. / 예약 전 항공사 공식 사이트에서 재확인',"
              "checked:'수집 기준: 2026-11-22 KST · 대한항공 공개 보너스 좌석 · 외항사 9개 프로그램 실측',start:'2026-11',end:'2027-11'}")

SHORT_ENTRY = ("  mileage:{sub:'대한항공(부산) + 외항사 9개 프로그램 보너스 좌석 · 통합 달력',"
               "checked:'조회 기준: 2026.11.22 KST'},")

HOOKS = [
    # (이름, 찾을 문자열, 바꿀 문자열)
    ('tabs 항목', None, None),
    ('짧은 항목', None, None),
    ('DATA_BUST',
     "mileage:'2026-11-22b','partner-mileage':'2026-11-22z49'",
     "mileage:'2026-11-22z73','mileage-pt':'2026-11-22z73'"),
    ('PART_FILE',
     "mileage:'tab8_mileage.json','partner-mileage':'tab9_partner_mileage.json'",
     "mileage:'tab8_mileage.json','mileage-pt':'tab9_partner_mileage.json'"),
    ('DATA_READY',
     "mileage:false,'partner-mileage':false",
     "mileage:false,'mileage-pt':false"),
    ('tabNeeds',
     "function tabNeeds(tab){\n  if(tab==='valet')return ['valet'];",
     "function tabNeeds(tab){\n  if(tab==='mileage')return ['mileage','mileage-pt'];\n  if(tab==='valet')return ['valet'];"),
    ('loadPart',
     ("    }else if(tab==='mileage'){\n"
      "      Object.assign(MGD,data);mgPrep();\n"
      "      if(st.tab==='mileage')renderMileage();\n"
      "    }else if(tab==='partner-mileage'){\n"
      "      Object.assign(PMD,data);pmPrep();\n"
      "      if(st.tab==='partner-mileage')renderPartner();\n"
      "    }"),
     ("    }else if(tab==='mileage'){\n"
      "      Object.assign(MGD,data);mlKEPrep();\n"
      "      if(st.tab==='mileage')renderMileage();\n"
      "    }else if(tab==='mileage-pt'){\n"
      "      PDS.PUS=data;PMD=data;ptPrep();\n"
      "      if(st.tab==='mileage')renderMileage();\n"
      "    }")),
    ('render() 디스패치',
     "  if(st.tab==='partner-mileage'){renderPartner();hashSync();return}\n",
     ""),
    ('setDealPanels',
     "const pp=document.getElementById('pmPanel');if(pp)pp.hidden=which!=='partner-mileage';",
     ""),
    ('해시 별칭',
     "function applyHashState(p){\n  let tab=p.get('tab');",
     "function applyHashState(p){\n  let tab=p.get('tab');\n  if(tab==='partner-mileage')tab='mileage';   /* 2026-11-22 통합 — 옛 ⑨ 외항사 주소는 ⑧ 마일리지발권으로 */"),
    ('hashchange 가드',
     "if(!p||!(tabs[p.get('tab')]||p.get('tab')==='china'||p.get('tab')==='domestic'))return;",
     "if(!p||!(tabs[p.get('tab')]||p.get('tab')==='partner-mileage'||p.get('tab')==='china'||p.get('tab')==='domestic'))return;"),
]


def cut(s, a, b, name):
    i = s.find(a)
    if i < 0:
        raise SystemExit('시작 표시를 찾지 못했습니다: %s (%r)' % (name, a[:40]))
    j = s.find(b, i)
    if j < 0:
        raise SystemExit('끝 표시를 찾지 못했습니다: %s (%r)' % (name, b[:40]))
    return s[:i] + s[j + len(b):]


def main(argv):
    check = '--check' in argv
    src = open(INDEX, encoding='utf-8').read()
    before = len(src)
    log = []

    # 1) 옛 ⑨ 외항사 탭 블록 걷어내기
    if '<!-- PARTNER:NAV -->' in src:
        src = cut(src, '<!-- PARTNER:NAV -->', '<!-- /PARTNER:NAV -->\n', 'PARTNER NAV')
        log.append('PARTNER NAV 제거')
    if '<!-- PARTNER:SECTION -->' in src:
        src = cut(src, '<!-- PARTNER:SECTION -->', '<!-- /PARTNER:SECTION -->\n', 'PARTNER SECTION')
        log.append('PARTNER SECTION 제거')
    if '/* PARTNER:CSS */' in src:
        src = cut(src, '/* PARTNER:CSS */', '/* /PARTNER:CSS */\n', 'PARTNER CSS')
        log.append('PARTNER CSS 제거')
    if '// PARTNER:JS' in src:
        src = cut(src, '// PARTNER:JS', '// /PARTNER:JS\n', 'PARTNER JS')
        log.append('PARTNER JS 제거')

    # 2) tabs 항목 — ⑧ 하나로 (⑨ 항목은 지운다)
    i = src.find("mileage:{title:'")
    if i >= 0:
        j = src.find('partner-mileage', i)
        if j >= 0:
            k = src.find(',valet:', j)
            if k < 0:
                raise SystemExit('tabs 의 valet 항목을 찾지 못했습니다')
            src = src[:i] + TABS_ENTRY + src[k:]
            log.append('tabs 항목 통합')
    # 3) 짧은 항목 — ⑧ 하나로
    m = re.search(r"  mileage:\{sub:'[^']*',checked:'[^']*'\},\n(?:  'partner-mileage':\{sub:'[^']*',checked:'[^']*'\},\n)?", src)
    if m:
        src = src[:m.start()] + SHORT_ENTRY + '\n' + src[m.end():]
        log.append('짧은 항목 통합')

    # 4) 연결 고리
    for name, old, new in HOOKS:
        if old is None:
            continue
        if new in src and new != '':
            log.append('%-14s 이미 됨' % name)
            continue
        if old not in src:
            log.append('%-14s !! 없음' % name)
            continue
        src = src.replace(old, new, 1)
        log.append('%-14s 적용' % name)

    # 5) 콤보 탭 — ⑧ 마일리지발권 바로 뒤(발렛 앞)로
    combo = re.search(r'\n? *<button class="tab combo-tab" data-tab="combo"[^\n]*</button>\n', src)
    if combo:
        tag = combo.group(0).strip('\n')
        src = src[:combo.start()] + '\n' + src[combo.end():]
        anchor = '<!-- /MILEAGE:NAV -->\n'
        if anchor not in src:
            raise SystemExit('MILEAGE:NAV 끝 표시를 찾지 못했습니다')
        pos = src.index(anchor) + len(anchor)
        src = src[:pos] + tag + '\n' + src[pos:]
        log.append('콤보 탭 자리 이동')

    print('\n'.join(log))
    print('index.html %d → %d bytes' % (before, len(src)))
    if 'partner-mileage' in src:
        for line in src.split('\n'):
            if 'partner-mileage' in line:
                print('남은 참조:', line.strip()[:160])
    if check:
        print('(--check: 쓰지 않았습니다)')
        return 0
    open(INDEX, 'w', encoding='utf-8').write(src)
    print('index.html 갱신 완료')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
