#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 아코르 536곳 — SNU(Suite Night Upgrade) 참여 상태 전수 재검사 (2026-11-22).

한진님 지시 — "폴더 2 SNU 적용호텔 다시 검사해봐" / "미참여 호텔에 다시 체크해".

무엇을 하나
  · 아코르 ALL 공식 「Suite Night Upgrade 참여 호텔」 목록을 그대로 받아
    (`data/accor_snu_official_20261122.json`, all.accor.com 공식 페이지가 부르는
     api.accor.com/catalog/v1/hotels?label=SUITE_NIGHT_UPGRADE) ② 아코르 536곳과 대조한다.
  · 대조 키는 ① 호텔 코드(공식 목록의 factsheetUrl /hotel/<코드>/), ② 영문 이름(정규화) 두 가지.
  · 호텔마다 `snu` 객체를 붙인다 — 네 가지 상태로 나눈다.
        participating    공식 참여 호텔          → SNU 쓸 수 있음
        hotel_excluded   참여 브랜드인데 개별 호텔은 공식 목록에 없음
        brand_excluded   애초에 공식 참여 브랜드 15개에 없는 브랜드
        unverified       공식 목록·아코르 카탈로그 어디에서도 호텔을 찾지 못함
  · 이미 `program`(Stay Plus/SNU)이 있던 51곳은 program.snu·snuBrand·snuNote 를
    같은 결론으로 맞춘다(Stay Plus 값은 건드리지 않는다).
  · 탭 공통 문구(accor.program.snuBrands·snuChecked·snuCounts)를 갱신하고
    갱신 이력(extended)에 이 작업을 적는다.

실행 (저장소 루트에서):
    python3 tools/merge_accor_snu_20261122.py            # master_db.json 수정
    python3 tools/merge_accor_snu_20261122.py --dry-run  # 확인만
"""
import collections
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
OFFICIAL = os.path.join(ROOT, 'data', 'accor_snu_official_20261122.json')

CHECKED = '2026-11-22'
STATUS_KO = {'participating': '참여', 'hotel_excluded': '개별 미참여',
             'brand_excluded': '브랜드 미참여', 'unverified': '확인 불가'}

# 아코르 공식 안내의 럭셔리·프리미엄 15개 브랜드(영문 소문자)
BRANDS = {'raffles', 'faena', 'delano', 'sofitel legend', 'fairmont', 'sls', 'so/',
          'sofitel', 'mgallery', '21c', 'mondrian', 'pullman', 'swissôtel',
          'mövenpick', 'grand mercure'}
# 우리 자료의 브랜드 표기(한글 포함) → 위 영문 표기
BRAND_KO = {'래플스': 'raffles', '페어몬트': 'fairmont', '소피텔': 'sofitel',
            '소피텔 레전드': 'sofitel legend', '풀만': 'pullman',
            '스위소텔': 'swissôtel', 'swissotel': 'swissôtel',
            '뫼벤픽': 'mövenpick', 'movenpick': 'mövenpick',
            'movenpick living': 'mövenpick living',
            '그랜드 머큐어': 'grand mercure', 'grand mercure': 'grand mercure',
            '엠갤러리': 'mgallery', 'm갤러리': 'mgallery', 'mgallery': 'mgallery',
            'so/': 'so/', '몬드리안': 'mondrian', 'mondrian': 'mondrian',
            '트라이브': 'tribe', 'tribe': 'tribe', 'rixos': 'rixos',
            '핸드라이튼 컬렉션': 'handwritten collection',
            'handwritten collection': 'handwritten collection'}

# 공식 목록과 아코르 카탈로그(중국 747곳) 어디에서도 찾지 못한 카드 — 2026-11-22 확인
UNVERIFIED = {'ap024', 'ap257'}

NOTE = ('2026-11-22 KST ② 아코르 SNU 재검사 — 아코르 ALL 공식 「Suite Night Upgrade 참여 호텔」 목록'
        '(all.accor.com, 2026-11-22 조회 · 대한민국·중국·홍콩·마카오·태국·베트남·싱가포르·인도네시아·'
        '필리핀·일본·캄보디아·말레이시아·호주·몰디브 14개국 295곳)과 536곳을 코드·영문 이름으로 대조해 '
        'SNU 참여 184곳(이전 28곳) · 개별 미참여 29곳 · 브랜드 미참여 321곳 · 확인 불가 2곳으로 나눴습니다. '
        '브랜드 원칙(참여 15개 브랜드)과 달리 공식 목록에 있는 예외 호텔(중국 머큐어·노보텔 일부, 태국 트라이브 푸켓 파통, '
        '푸켓 스플래시 비치, 푸꾸옥 리소스, 상하이 홍차오 핸드라이튼 등)은 참여로 적었고, '
        '페어몬트 서울·몬드리안 서울 이태원은 참여로 바로잡았습니다(이전에는 확인 창에 SNU 요금이 안 떠 미노출로 적혀 있었음). '
        '그랜드 머큐어 서울 용산은 공식 목록에 없어 미참여로 바로잡았습니다.')


def norm(s):
    s = (s or '').lower().replace('’', "'").replace('&', ' and ')
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


# brand 칸이 빈 카드(통합 전 아코르 카드 14곳)는 이름 앞머리로 브랜드를 알아본다
NAME_BRAND = [('grand mercure', 'grand mercure'), ('sofitel legend', 'sofitel legend'),
              ('fairmont', 'fairmont'), ('sofitel', 'sofitel'), ('pullman', 'pullman'),
              ('swissôtel', 'swissôtel'), ('swissotel', 'swissôtel'),
              ('mövenpick', 'mövenpick'), ('movenpick', 'mövenpick'),
              ('mgallery', 'mgallery'), ('raffles', 'raffles'), ('mondrian', 'mondrian'),
              ('so/', 'so/'), ('rixos', 'rixos'), ('tribe', 'tribe'),
              ('handwritten', 'handwritten collection')]


def brand_key(b):
    b = (b or '').strip().lower()
    return BRAND_KO.get(b, b)


def brand_of(h):
    bk = brand_key(h.get('brand'))
    if bk in BRANDS or bk in ('tribe', 'rixos', 'handwritten collection', 'movenpick living'):
        return bk
    for text in (h.get('english') or '', h.get('name') or ''):
        lo = text.strip().lower()
        for pat, b in NAME_BRAND:
            if lo.startswith(pat):
                return b
    ko = (h.get('name') or '')
    for k, b in (('그랜드 머큐어', 'grand mercure'), ('소피텔', 'sofitel'), ('페어몬트', 'fairmont'),
                 ('풀만', 'pullman'), ('스위소텔', 'swissôtel'), ('뫼벤픽', 'mövenpick'),
                 ('래플스', 'raffles'), ('몬드리안', 'mondrian'), ('엠갤러리', 'mgallery'),
                 ('M갤러리', 'mgallery'), ('트라이브', 'tribe')):
        if k in ko:
            return b
    return bk


def build_index(off):
    by_code, by_name = {}, {}
    for slug, c in off['countries'].items():
        for h in c['hotels']:
            by_code[h['code']] = (h, slug)
            by_name[norm(h['name'])] = (h, slug)
    return by_code, by_name


def classify(h, by_code, by_name):
    o = None
    if h.get('code') and h['code'] in by_code:
        o = by_code[h['code']]
    elif norm(h.get('english')) in by_name:
        o = by_name[norm(h.get('english'))]
    elif norm(h.get('name')) in by_name:
        o = by_name[norm(h.get('name'))]
    bk = brand_of(h)
    in_brand = bk in BRANDS
    if h['id'] in UNVERIFIED:
        status = 'unverified'
    elif o:
        status = 'participating'
    elif in_brand:
        status = 'hotel_excluded'
    else:
        status = 'brand_excluded'
    return status, in_brand, o


def note_of(h, status, in_brand, o):
    opening = 'Opening' in (h.get('english') or '') or '개관 예정' in (h.get('name') or '')
    if status == 'participating':
        base = ('SNU 참여 — 아코르 공식 참여 호텔(%s 확인)' % CHECKED if in_brand else
                'SNU 참여 — 브랜드 원칙엔 없는 예외 호텔(아코르 공식 참여 목록, %s)' % CHECKED)
        if opening:
            base += ' · 개관 예정 호텔'
    elif status == 'hotel_excluded':
        base = ('SNU 미참여 — 참여 브랜드이나 이 호텔은 공식 참여 목록에 없음(%s). '
                '룸과 스위트를 함께 갖춘 호텔만 참여할 수 있어 전객실 스위트·빌라·레지던스형은 빠집니다' % CHECKED)
    elif status == 'brand_excluded':
        base = 'SNU 미참여 브랜드 — 아코르 공식 참여 브랜드 15개에 없음(%s)' % CHECKED
    else:
        base = 'SNU 확인 불가 — 공식 참여 목록과 아코르 카탈로그에서 호텔을 찾지 못함(%s)' % CHECKED
    return base


def main(argv):
    dry = '--dry-run' in argv
    db = json.load(open(MASTER, encoding='utf-8'))
    off = json.load(open(OFFICIAL, encoding='utf-8'))
    by_code, by_name = build_index(off)

    accor = [h for h in db['hotels'] if h.get('group') == 'accor']
    stats = collections.Counter()
    by_zone = collections.Counter()
    flipped_in, flipped_out = [], []
    examples = collections.Counter()

    for h in accor:
        old = h.get('snu') or {}
        old_status = old.get('status')
        old_snu = (h.get('program') or {}).get('snu')
        status, in_brand, o = classify(h, by_code, by_name)
        note = note_of(h, status, in_brand, o)
        old_note = (h.get('program') or {}).get('snuNote')
        # 예전 메모(창별 SNU 요금 관측 등)는 지우지 않고 뒤에 붙인다
        if old_note and ('창' in old_note or '미노출' in old_note) and old_note not in note:
            row = dict(h.get('snu') or {})
            row['observed'] = old_note
        else:
            row = dict(h.get('snu') or {})
        row.update({'status': status, 'brand': in_brand, 'checked': CHECKED, 'note': note})
        if o:
            row['officialName'] = o[0]['name']
            if h.get('code') != o[0]['code']:
                row['officialCode'] = o[0]['code']
        h['snu'] = row

        p = h.get('program')
        if isinstance(p, dict):
            p['snu'] = (status == 'participating')
            p['snuBrand'] = in_brand
            p['snuNote'] = note if not row.get('observed') else note + ' · ' + row['observed']

        stats[status] += 1
        by_zone[(h.get('zone'), status)] += 1
        if status == 'participating' and old_snu is not True:
            flipped_in.append(h)
        if status != 'participating' and old_snu is True:
            flipped_out.append(h)
        if status == 'participating' and not in_brand:
            examples[h.get('brand')] += 1

    prog = db['accor'].setdefault('program', {})
    prog['snuBrands'] = ('SNU 참여 15개 브랜드: 래플스(Raffles)·파에나·델라노·소피텔 레전드·페어몬트·SLS·SO/·소피텔·MGallery·21c·'
                         '몬드리안·풀만·스위소텔·뫼벤픽·그랜드 머큐어 / 이 브랜드 안에서도 호텔별로 참여가 갈리고, '
                         '공식 목록에 있는 호텔만 쓸 수 있습니다. 노보텔·머큐어·이비스(스타일·버짓)·아다지오·트라이브·'
                         '핸드라이튼 컬렉션·반얀트리·앙사나·카시아·가와·세벨 등은 원칙 제외이나 개별 예외 호텔이 있습니다.')
    prog['snuChecked'] = CHECKED + ' KST · all.accor.com 공식 SNU 참여 호텔 목록 295곳(14개국) 대조'
    prog['snuCounts'] = {'hotels': len(accor),
                         'participating': stats['participating'],
                         'hotelExcluded': stats['hotel_excluded'],
                         'brandExcluded': stats['brand_excluded'],
                         'unverified': stats['unverified']}

    db['generated_at'] = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    ext = str(db.get('extended') or '')
    if NOTE not in ext:
        db['extended'] = (ext + ' / ' + NOTE) if ext else NOTE

    print('② 아코르 %d곳' % len(accor))
    for k in ('participating', 'hotel_excluded', 'brand_excluded', 'unverified'):
        print('  %-16s %s %4d곳' % (STATUS_KO[k], k, stats[k]))
    print('  지역별:', dict(sorted(((z, s), n) for (z, s), n in by_zone.items())))
    print('  참여로 바뀐 카드 %d곳 · 미참여로 바뀐 카드 %d곳' % (len(flipped_in), len(flipped_out)))
    for h in flipped_out:
        print('    ↓', h['id'], h['name'], '→', h['snu']['status'])
    print('  브랜드 원칙 밖 예외 참여:', dict(examples))
    if not dry:
        tmp = MASTER + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fp:
            json.dump(db, fp, ensure_ascii=False, indent=1)
            fp.write('\n')
        os.replace(tmp, MASTER)
        print('wrote %s' % os.path.relpath(MASTER, ROOT))
    else:
        print('--dry-run — 파일을 쓰지 않았습니다.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
