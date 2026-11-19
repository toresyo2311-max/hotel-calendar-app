#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""🛫 공항 라운지 탭 데이터 생성기 — `data/app/lounge.json`.

보유 카드 58장(=`data/app/valet.json` 의 myCards)을 카드사·국제브랜드사 공식
안내(상품설명서·선택서비스 안내장·더라운지 제휴카드 목록)로 확인한 공항라운지
혜택만 옮긴다.

원칙(2026-11-20):
  · 확인하지 못한 조건은 비워 두고(0/null) 화면에서 "확인 필요"로 보여 준다.
  · 카드 이름 그대로의 판본 기준. 브랜드(VISA/Master/UnionPay)에 따라 조건이
    다르면 note 에 적고, 판본 자체가 미확정인 카드는 status='unknown'.
  · status:
      eligible → 공식 안내에 무료 라운지 제공이 확인됨
      none     → 공식 상품 안내·라운지 프로그램 대상 목록에서 제공 없음 확인
      unknown  → 판본·상품명이 미확정이라 확인 불가(추정 금지)

사용법(저장소 루트에서):
    python3 tools/lounge_db.py build     # data/app/lounge.json 생성
    python3 tools/lounge_db.py check     # 순번·정합성만 검사
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'app', 'lounge.json')
VALET = os.path.join(ROOT, 'data', 'app', 'valet.json')

BASIS_DATE = '2026-11-20'
BASIS = ('카드사 상품설명서·국제브랜드 선택서비스 안내장과 더라운지(THE LOUNGE) 제휴카드 '
         '공식 목록(2026년 기준)에서 확인한 값입니다. 같은 카드라도 발급 브랜드'
         '(VISA·Mastercard·UnionPay·국내전용)와 판본에 따라 횟수·조건이 달라질 수 있어 '
         '출국 전 카드사 앱에서 잔여 횟수를 확인해야 합니다. 카드사 사정으로 바뀔 수 있습니다.')

NETWORKS = [
    {'id': 'the_lounge', 'name': '더라운지', 'desc': 'THE LOUNGE 앱에서 카드 등록 후 이용권 발급 — 전 세계 1,300여 개 제휴 라운지'},
    {'id': 'brand', 'name': '브랜드 직접', 'desc': '카드 제시로 스카이허브·마티나·아시아나 라운지에 바로 입장(국제브랜드 선택서비스)'},
    {'id': 'amex', 'name': '아멕스 라운지', 'desc': 'American Express Global Lounge Collection — 센추리언·델타 스카이클럽 등'},
    {'id': 'pp', 'name': 'Priority Pass', 'desc': '실물 PP 카드 제시 — 보유 카드 중 해당 없음'},
]

AIRPORTS = [
    {'id': 'icn1', 'name': '인천 T1', 'desc': '스카이허브(동·서·탑승동) · 마티나(동·서) · 아시아나 라운지'},
    {'id': 'icn2', 'name': '인천 T2', 'desc': '스카이허브(동·서) · 마티나(중앙)'},
    {'id': 'gmp', 'name': '김포', 'desc': '국제선 스카이허브 · 아시아나 라운지'},
    {'id': 'pus', 'name': '김해', 'desc': '국제선 스카이허브 · 아시아나 라운지'},
    {'id': 'intl', 'name': '해외', 'desc': '더라운지·아멕스 제휴 해외 공항 라운지'},
]

# ────────────────────────────────────────────────────────────────
# 보유 카드 58장 — valet.json 의 myCards 와 같은 순번·이름
#   (seq, status, networks, airports, monthly, annual, daily, companion, prev, url, note, basis)
#   companion: (무료 동반 인원, 비고)
#   prev: (전월 실적 원, 표기)
# ────────────────────────────────────────────────────────────────
NO = ('none', [], [], None, None, None, (0, '본인만'), None, None,
      '카드사 공항라운지 프로그램(더라운지 제휴·국제브랜드 선택서비스) 대상 목록에 없고, 공식 상품 페이지의 혜택에도 라운지 항목이 확인되지 않았습니다.', 'program')

CARDS = {
    1: ('none', [], [], None, None, None, (0, '본인만'), None, None,
        'IBK 참! 좋은 시리즈는 할인 특화 상품으로, IBK 공항라운지 제공 카드(BLISS·K22·I-Mileage 등)에 들지 않습니다.', 'program'),
    2: NO,
    3: ('none', [], [], None, None, None, (0, '본인만'), None,
        'https://m.hanacard.co.kr/leaflet/15/15272_20250116.pdf',
        '하나 MG+ Blue 상품설명서 혜택은 일상 청구할인뿐입니다. 라운지는 같은 MG+ 라인의 BLACK 판본에만 있습니다.', 'official'),
    4: NO,
    5: ('none', [], [], None, None, None, (0, '본인만'), None,
        'https://www.lottecard.co.kr/app/LPCDAEB_V100.lc?vtCdKndC=C00548-A00548',
        '롯데 VISA PLATINUM 서비스 안내(02)가 이 상품의 인천·김포·김해 발렛과 공항라운지 서비스를 제공하지 않는다고 명시합니다. 2026-05-29 신규 발급 중단.', 'official'),
    6: NO,
    7: NO,
    8: ('unknown', [], [], None, None, None, (0, ''), None, None,
        '상품명이 확정되지 않은 후보 카드입니다(동아-대구은행 대한항공 마일리지).', 'unknown'),
    9: ('none', [], [], None, None, None, (0, '본인만'), None,
        'https://card.kbcard.com/CRD/DVIEW/HCAMCXPRICAC0076?cooperationcode=07964&mainCC=a',
        '노리2 체크카드(KB Pay) 혜택에 라운지가 없습니다. 같은 이름의 (Global) 판본만 더라운지 연 1회(전월 30만원)를 제공하며, 두 판본은 실적이 합산되지 않습니다.', 'official'),
    10: ('eligible', ['brand'], ['icn1', 'icn2', 'gmp', 'pus'], None, 2, 1, (0, '동반자 입장료 본인 부담'), (300000, '전월 30만원'),
         'https://www.shinhancard.com/pconts/download/card/MO_26_00789_master_platinum_2_classics.pdf',
         'Mastercard Platinum 발급본 기준 스카이허브·마티나 통합 연 2회. The CLASSIC-Y는 신규 발급월에 전월 실적 서비스가 제공되지 않습니다. UnionPay 발급본은 별도 안내를 확인하세요.', 'official'),
    11: NO,
    12: NO,
    13: NO,
    14: NO,
    15: ('eligible', ['brand'], ['icn1', 'icn2', 'gmp', 'pus'], None, 2, 1, (0, '동반자 유료(아시아나 탑승권 소지 시)'), None,
         'https://card.kbcard.com/BON/DVIEW/HBCMCXPRISVC0053',
         'KB 플래티늄 쿠폰형 — Mastercard 발급본에 아시아나 라운지·SKY HUB 통합 연 2회(일 1회, 본인만). 쿠폰형은 전월 실적 조건이 없습니다. VISA 발급본은 KB 선택서비스 표에 라운지가 없어 카드 앞면 브랜드를 확인해야 합니다.', 'official'),
    16: NO,
    17: ('eligible', ['the_lounge'], ['icn1', 'icn2', 'gmp', 'pus', 'intl'], 2, 10, None, (1, '본인+동반 1인(동반 시 2회 차감)'), (500000, '전월 50만원'),
         'https://pc.wooricard.com/dcpc/yh1/cct/cct11/prdntc/H1CCT211S09.do',
         '더라운지 앱 이용권 — 국내외 공항 통합 월 2회·연 10회. 본인카드만 제공(가족카드 불가), 동반인 단독 사용 불가.', 'official'),
    18: NO,
    19: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://www.samsungcard.com/home/card/cardinfo/PGHPPCCCardCardinfoDetails001?code=AAP1767',
         '삼성 iD SIMPLE 혜택은 OTT·간편결제·편의점·배달 할인뿐입니다. 라운지는 iD GLOBAL·THE iD. 라인에 있습니다.', 'official'),
    20: NO,
    21: NO,
    22: ('unknown', [], [], None, None, None, (0, ''), None, None,
        'SKYPASS 롯데카드(신용)는 단종 상품이고, 롯데의 공항라운지는 SKYPASS 롯데 플래티넘(연회비 12만원) 판본에만 확인됩니다. 보유 판본을 확인해야 합니다.', 'unknown'),
    23: NO,
    24: ('eligible', ['the_lounge'], ['icn1', 'icn2', 'gmp', 'pus', 'intl'], None, 10, None, (0, '본인만(가족·동반 불가)'), (500000, '전월 50만원'),
         'https://m.theloungemembers.com/renew/search/affiliate-card/lists?searchMode=keyword&cardName=the%20Green',
         '더라운지 제휴카드 목록 기준 the Green(기본 판본) 연 10회. 계열 판본에 따라 다릅니다 — Edition2 월 2회·연 10회, Edition3·4 연 5회. 카드 앞면의 Edition 표기를 확인하세요.', 'official'),
    25: NO,
    26: ('unknown', [], [], None, None, None, (0, ''), None, None,
        'iM 스카이패스 V2 Gold는 해외겸용(Mastercard) 본인만 월 1회·연 2회(전월 30만원)이고 국내전용(BC)은 라운지가 없습니다. 보유 판본이 확정되지 않았습니다.', 'unknown'),
    27: NO,
    28: ('unknown', [], [], None, None, None, (0, ''), None, None,
        '발급사·유형·상품명이 확정되지 않은 카드입니다(CJ카드 패스-신).', 'unknown'),
    29: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://card.kbcard.com/cards/products/check-cards/kb-travelers-check-card',
         '트래블러스 체크카드 기본 혜택에 라운지가 없습니다. 해외 이용 실적을 채우면 라운지 이용권을 100원에 사는 기간 한정 행사만 있습니다.', 'official'),
    30: ('unknown', [], [], None, None, None, (0, ''), None, None,
        '상품명이 확정되지 않은 후보 카드입니다(BNK 스카이패스).', 'unknown'),
    31: ('none', [], [], None, None, None, (0, '본인만'), None, None,
        '교통 전용 상품으로 공항라운지 혜택이 없습니다.', 'program'),
    32: NO,
    33: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://m.hanacard.co.kr/MKCDCM1000M.web?CD_PD_SEQ=15406&cateType=MKCDPD2000M',
         '트래블로그 체크카드 혜택은 환전·해외 수수료 면제와 하나머니 적립뿐입니다. 라운지는 트래블로그 신용(SKYPASS·PRESTIGE) 판본에만 있습니다.', 'official'),
    34: NO,
    35: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://m.hanacard.co.kr/MKCDCM1000M.web?CD_PD_SEQ=15406&cateType=MKCDPD2000M',
         '트래블로그 체크카드 혜택은 환전·해외 수수료 면제와 하나머니 적립뿐입니다. 라운지는 트래블로그 신용(SKYPASS·PRESTIGE) 판본에만 있습니다.', 'official'),
    36: ('unknown', [], [], None, None, None, (0, ''), None, None,
        '네이버페이 머니카드(신용)의 라운지와 다른 하나 체크 판본으로, 공식 안내에서 라운지 제공을 확인하지 못했습니다.', 'unknown'),
    37: NO,
    38: NO,
    39: NO,
    40: ('none', [], [], None, None, None, (0, '본인만'), None, None,
         '현대백화점 멤버십 전용 카드로 공항라운지 혜택이 없습니다.', 'program'),
    41: ('unknown', [], [], None, None, None, (0, ''), None, None,
        'BC 아시아나클럽카드는 연간 실적에 따라 라운지 연 3회~무제한이 확인되지만, BNK부산은행 발급 판본의 조건은 공식 안내에서 확인하지 못했습니다.', 'unknown'),
    42: ('eligible', ['the_lounge', 'amex'], ['icn1', 'icn2', 'gmp', 'pus', 'intl'], None, 10, 1, (0, '동반자 입장료 별도'), (500000, '전월 50만원'),
         'https://www.hyundaicard.com/docfiles/resources/pc/html/carDtl/AMPT_PC.html',
         '더라운지 전 세계 라운지 일 1회·연 10회(본인만). 별도로 American Express Global Lounge Collection(센추리언·델타 스카이클럽)이 제공됩니다. 신규 발급 시 3개월간 실적 무관.', 'official'),
    43: ('unknown', [], [], None, None, None, (0, ''), None, None,
        '상품명이 확정되지 않은 후보 카드입니다(IBK 스카이패스).', 'unknown'),
    44: NO,
    45: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://card.tickettime.co.kr/card/%ED%95%98%EB%82%98%EC%B9%B4%EB%93%9C-%EC%9D%B8%ED%84%B0%ED%8C%8C%ED%81%AC-%ED%88%AC%EC%96%B4-%EC%8A%A4%EC%B9%B4%EC%9D%B4%ED%8C%A8%EC%8A%A4-%EC%B9%B4%EB%93%9C-1707',
         '카드 비교공시 원문 혜택(인터파크투어 적립·항공권 할인)에 라운지가 없습니다.', 'program'),
    46: ('none', [], [], None, None, None, (0, '본인만'), None, None,
         'Liiv Mate 카드 혜택은 포인트리 적립·할인뿐입니다. 마스터 티타늄 라운지(연 2회)는 Liiv M 카드 등 다른 상품입니다.', 'program'),
    47: ('eligible', ['the_lounge'], ['icn1', 'icn2', 'gmp', 'pus', 'intl'], None, 4, None, (1, '본인+동반 1인(동반 시 1회 차감)'), (300000, '전월 30만원'),
         'https://www.shinhancard.com/pconts/html/card/apply/premium/1200288_2205.html',
         '더라운지 앱 이용권 연 4회 — 본인 및 동반 1인까지 무료(동반 시 이용권 1매 추가, 횟수 차감). 본인카드만 제공, 연 기준은 1~12월.', 'official'),
    48: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://www.shinhancard.com/pconts/html/card/apply/credit/1188291_2207.html',
         'Always On 혜택은 포인트 적립·영화 할인뿐입니다(2018-05-02 순신규 발급 중단).', 'official'),
    49: NO,
    50: ('none', [], [], None, None, None, (0, '본인만'), None,
         'https://www.green-card.co.kr/app/customer/customerListPage.do',
         '그린카드(전국형) 혜택은 에코머니 적립·문화시설 할인뿐입니다.', 'official'),
    51: ('eligible', ['the_lounge'], ['icn1', 'icn2', 'gmp', 'pus', 'intl'], 1, 2, None, (0, '본인만'), (300000, '전월 국내 30만원'),
         'https://m.theloungemembers.com/renew/search/affiliate-card/lists?searchMode=keyword&cardName=UniMile',
         '더라운지 앱 이용권 — 국내외 공항 월 1회·연 2회. UnionPay 브랜드 발급본만 제공되며 국내전용(BC)은 제공되지 않습니다. 카드 수령 등록일부터 다음달 말일까지는 30만원 이용 시 그다음 날부터 제공.', 'official'),
    52: ('none', [], [], None, None, None, (0, '본인만'), None, None, '법인카드로 공항라운지 혜택이 없습니다.', 'program'),
    53: ('none', [], [], None, None, None, (0, '본인만'), None, None, '법인카드로 공항라운지 혜택이 없습니다.', 'program'),
    54: ('none', [], [], None, None, None, (0, '본인만'), None, None, '선불카드로 공항라운지 혜택이 없습니다.', 'program'),
    55: ('none', [], [], None, None, None, (0, '본인만'), None, None, '선불카드로 공항라운지 혜택이 없습니다.', 'program'),
    56: ('none', [], [], None, None, None, (0, '본인만'), None, None, '선불카드로 공항라운지 혜택이 없습니다.', 'program'),
    57: ('none', [], [], None, None, None, (0, '본인만'), None, None, '선불카드로 공항라운지 혜택이 없습니다.', 'program'),
    58: ('none', [], [], None, None, None, (0, '본인만'), None, None, '선불카드로 공항라운지 혜택이 없습니다.', 'program'),
}


def build():
    valet = json.load(open(VALET, encoding='utf-8'))
    out = []
    problems = []
    for c in valet['myCards']:
        seq = c['seq']
        spec = CARDS.get(seq)
        if spec is None:
            problems.append('myCards %d: 라운지 조사 값이 없습니다' % seq)
            spec = NO
        (status, networks, airports, monthly, annual, daily, comp, prev, url, note, basis) = spec
        item = dict(
            seq=seq, issuer=c['issuer'], name=c['name'], type=c['type'],
            status=status, networks=list(networks), airports=list(airports),
            monthly=monthly, annual=annual, daily=daily,
            companion_free=comp[0], companion_note=comp[1],
            prev_n=(prev[0] if prev else None), prev_label=(prev[1] if prev else '조건 없음'),
            official_url=url, note=note, basis=basis,
            status_note=c.get('status_note'),
        )
        if status == 'eligible' and not (monthly or annual):
            problems.append('myCards %d: eligible 인데 횟수가 비었습니다' % seq)
        if status == 'none' and (annual or monthly):
            problems.append('myCards %d: none 인데 횟수가 있습니다' % seq)
        out.append(item)
    cnt = {'my_cards': len(out),
           'eligible': sum(1 for x in out if x['status'] == 'eligible'),
           'none': sum(1 for x in out if x['status'] == 'none'),
           'unknown': sum(1 for x in out if x['status'] == 'unknown'),
           'annual_free_total': sum((x['annual'] or 0) for x in out),
           'with_companion': sum(1 for x in out if x['companion_free'] > 0),
           'networks': len([n for n in NETWORKS]),
           'official': sum(1 for x in out if x['basis'] == 'official')}
    data = dict(schema='teambusan.lounge.v1', generated=BASIS_DATE, basis=BASIS,
                networks=NETWORKS, airports=AIRPORTS, cards=out, counts=cnt)
    return data, problems


def main():
    cmds = set(sys.argv[1:]) or {'build'}
    data, problems = build()
    if problems:
        print('문제 %d건' % len(problems))
        for p in problems:
            print('  - ' + p)
    if 'build' in cmds and not problems:
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        print('저장 %s — 카드 %d장(가능 %d · 없음 %d · 미확정 %d) · 연간 무료 %d회'
              % (OUT, data['counts']['my_cards'], data['counts']['eligible'],
                 data['counts']['none'], data['counts']['unknown'],
                 data['counts']['annual_free_total']))
    elif not problems:
        print('정합성 OK — 카드 %d장' % data['counts']['my_cards'])
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
