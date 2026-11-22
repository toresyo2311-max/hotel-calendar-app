#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""⑨ IHG 아시아·오세아니아 72곳 → data/app/tab11_ihg.json

원자료: work/ihg/*.json 10개 묶음(한국 9 · 일본 19 · 대만 7 · 중국 8 · 홍콩/마카오 3 ·
        동남아 17 · 오세아니아 9 = 72곳) + work/ihg/ihg_asia_oceania_hotels.json(메타 72곳).
        각 묶음은 2026-11-22 비로그인 조회로 2026-12-01~2027-11-30(365일) 현금·포인트를 담았다.

출력 형식은 ⑧ 하얏트(tab10_hyatt.json)를 그대로 따른다 — 날짜는 {$d,$v} 압축 열,
현금은 rates, 포인트는 points. 값이 없는 칸은 null(0원·포인트 아님).

브랜드 코드(qSHBrC)는 실측값을 쓰되 묶음마다 다른 표기(RE·VX)는 요금 페이지가 정상 로드되는
표기(REGENT·VIGNETTE)로 맞춘다 — 2026-11-22 브라우저 실측(DADHO=VIGNETTE · PQCRR=REGENT ·
TPEKM=KIMPTON · TPENT=INDIGO · SEOHA=IC).

예약 URL은 브랜드 경로 + find-hotels/select-roomrate 형식이다.
  {brand_path}/hotels/kr/ko/find-hotels/select-roomrate
    ?fromRedirect=true&qSrt=sBR&qErm=false&qSlH={code}&qRms=1&qAdlt=2&qChld=0
    &qCiD={d}&qCiMy={(m-1):02d}{yyyy}&qCoD={d2}&qCoMy={(m2-1):02d}{yyyy2}
    &qAAR=&qRtP=6CBARC&setPMCookies=true&qSHBrC={brand_code}&qDest={dest}
    &qpMbw=0&qpMn=1&srb_u=1
  (qCiMy = 월-1 두 자리 + 연도. 브랜드 경로가 없는 /hotels/kr/ko/... 형식과 qDest·fromRedirect 가
   빠진 주소는 404로 떨어진다 — 2026-11-22 실측.)
"""
import json
import os
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WS = os.path.dirname(ROOT)
SRC = os.path.join(WS, 'work', 'ihg')
MASTER = os.path.join(SRC, 'ihg_asia_oceania_hotels.json')
BATCHES = [
    'ihg_kr_9_complete.json', 'jp_tokyo_8.json', 'jp_osaka_kyoto_6.json',
    'jp_fuk_oka_spk_5.json', 'tw_7.json', 'cn_8.json', 'hk_mo_sg_id_6.json',
    'th_7.json', 'vn_7.json', 'oc_9.json',
]
OUT = os.path.join(ROOT, 'data', 'app', 'tab11_ihg.json')

START, END = date(2026, 12, 1), date(2027, 11, 30)
DATES = []
_c = START
while _c <= END:
    DATES.append(_c.isoformat())
    _c += timedelta(days=1)

# 브랜드 한글 이름 — 화면 태그·필터에 쓴다
BRAND_KO = {
    'IC': '인터컨티넨탈', 'VOCO': '보코', 'HIX': '홀리데이 인 익스프레스',
    'HI': '홀리데이 인', 'CP': '크라운 플라자', 'KIMPTON': '킴프턴',
    'INDIGO': '호텔 인디고', 'REGENT': '리젠트', 'VIGNETTE': '비네트 컬렉션',
}
# 요금 페이지가 정상 로드되는 qSHBrC 표기로 맞춘다(2026-11-22 브라우저 실측)
BRAND_Q_FIX = {'RE': 'REGENT', 'VX': 'VIGNETTE'}
# 브랜드별 대표 qSHBrC — 자료에 값이 없을 때만 쓴다(추정 금지 원칙: 72곳 모두 실측값이 있다)
BRAND_Q = {'IC': 'IC', 'VOCO': 'VO', 'HIX': 'HX', 'HI': 'HI', 'CP': 'CP',
           'KIMPTON': 'KIMPTON', 'INDIGO': 'INDIGO', 'REGENT': 'REGENT',
           'VIGNETTE': 'VIGNETTE'}

# 자료 묶음마다 다른 필드 이름을 하나로 모은다
def q_of(rec):
    for k in ('qSHBrC', 'brand_code_qSHBrC', 'brand_code'):
        v = rec.get(k)
        if v:
            return str(v).strip()
    return None


def compact(series, code):
    """{'$d','$v'} 또는 날짜 키 dict → 365칸 압축 열"""
    if not series:
        return None
    if isinstance(series, dict) and '$v' in series:
        base = date.fromisoformat(series['$d'])
        vals = []
        for i in range(len(DATES)):
            d = (base + timedelta(days=i)).isoformat()
            idx = i
            v = series['$v'][idx] if idx < len(series['$v']) else None
            vals.append(int(round(v)) if isinstance(v, (int, float)) and v >= 0 else None)
        return {'$d': DATES[0], '$v': vals}
    vals = []
    for d in DATES:
        v = series.get(d)
        vals.append(int(round(v)) if isinstance(v, (int, float)) and v >= 0 else None)
    return {'$d': DATES[0], '$v': vals}


def null_runs(vals):
    runs, cur = [], []
    for i, v in enumerate(vals):
        if v is None:
            cur.append(i)
        else:
            if cur:
                runs.append((DATES[cur[0]], DATES[cur[-1]], len(cur)))
                cur = []
    if cur:
        runs.append((DATES[cur[0]], DATES[cur[-1]], len(cur)))
    return runs


# 호텔별로 반드시 남겨야 하는 특이사항 — 원자료에 적힌 사실만 한 줄로 옮긴다
SPEC_NOTE = {
    'OKAOU': '현금 2027-01-28~03-10(42일)·포인트 2027-02-01~03-10(38일)은 값이 없다(휴장·판매 중지 여부 원인 미확인).',
    'HKGLR': '2027-09-01~11-30은 판매 자체가 없다(2027-08-31 이후 달력이 끊김).',
}


def first_sentences(text, limit=200):
    t = ' '.join(str(text or '').split())
    if len(t) <= limit:
        return t
    out = ''
    for part in t.replace('. ', '.\n').split('\n'):
        if not part:
            continue
        if len(out) + len(part) + 1 > limit:
            break
        out = (out + ' ' + part).strip()
    if not out:
        out = t[:limit].rstrip() + '…'
    return out


def build_note(raw, code, rvals, pvals):
    """화면에 들어갈 한 줄 요약 — 원자료 문장 + (자료에 없을 때만) 실측 일수·빈 구간·예약창."""
    t = ' '.join(str(raw or '').split())
    head = first_sentences(t)
    parts = [head] if head else []
    if code in SPEC_NOTE:
        parts.append(SPEC_NOTE[code])
    has_counts = bool(__import__('re').search(r'(현금|포인트)\s*\d+\s*일', t))
    if not has_counts:
        parts.append('현금 %d일 / 포인트 %d일 실측(2026-12-01~2027-11-30).'
                     % (sum(1 for v in rvals if v), sum(1 for v in pvals if v)))
        gc = short_runs([r for r in null_runs(rvals) if r[2] >= 2])
        gp = short_runs([r for r in null_runs(pvals) if r[2] >= 2])
        gaps = []
        if gc:
            gaps.append('현금 ' + gc)
        if gp and gp != gc:
            gaps.append('포인트 ' + gp)
        if gaps and '값 없는' not in t:
            parts.append('값 없는 구간: ' + ' · '.join(gaps) + '.')
    if '2027-11-07' not in t:
        parts.append('2027-11-07~11-30은 예약창 미오픈(null).')
    note = ' '.join(p for p in parts if p)
    if len(note) > 360:
        note = note[:357].rstrip() + '…'
    return note


def short_runs(runs, cap=3, minlen=1):
    out = [r for r in runs if r[2] >= minlen]
    txt = []
    for a, b, n in out[:cap]:
        txt.append(a if a == b else a + '~' + b)
    return ', '.join(txt) + ('' if len(out) <= cap else ' 외')


def main():
    with open(MASTER, encoding='utf-8') as f:
        master = json.load(f)['hotels']
    by_code = {}
    for fn in BATCHES:
        with open(os.path.join(SRC, fn), encoding='utf-8') as f:
            doc = json.load(f)
        items = doc.get('hotels', doc) if isinstance(doc, dict) else doc
        for rec in items:
            code = str(rec.get('code', '')).strip().upper()
            if code:
                by_code[code] = rec

    hotels, problems = [], []
    for m in master:
        code = m['hotel_code'].upper()
        rec = by_code.get(code)
        if not rec:
            problems.append('원자료 없음: ' + code)
            continue
        rates = compact(rec.get('rates'), code)
        points = compact(rec.get('points'), code)
        if not rates or len(rates['$v']) != len(DATES):
            problems.append('현금 365칸 아님: ' + code)
            continue
        if not points or len(points['$v']) != len(DATES):
            problems.append('포인트 365칸 아님: ' + code)
            continue

        brand = m['brand']
        q = q_of(rec) or BRAND_Q.get(brand)
        q = BRAND_Q_FIX.get(q, q)
        detail = m.get('detail_url') or rec.get('detail_url') or ''
        # 브랜드 경로는 호텔 상세 주소에서 가져온다(/intercontinental/hotels/…)
        brand_path = detail.split('/hotels/')[0].rstrip('/').split('/')[-1] if '/hotels/' in detail else ''
        if not brand_path:
            problems.append('브랜드 경로 없음: ' + code)

        rvals, pvals = rates['$v'], points['$v']
        note = build_note(rec.get('note') or '', code, rvals, pvals)
        hotels.append({
            'id': m['id'],
            'group': 'ihg',
            'code': code,
            'brand': BRAND_KO.get(brand, brand),
            'brand_code': q,
            'brand_key': brand,
            'brand_path': brand_path,
            'region': m['region'],
            'city': m['city'],
            'country': m.get('country'),
            'name': m['name_ko'],
            'english': m['name_en'],
            'rates': rates,
            'points': points,
            'note': note,
            'source': (rec.get('source') or rec.get('source_cash') or
                       'www.ihg.com 비로그인 조회 · 세금 및 수수료 포함 · 성인2인 1실 · KRW · 2026-11-22'),
            'cells': {'rates': sum(1 for v in rvals if v), 'points': sum(1 for v in pvals if v)},
        })

    # 지표
    cells = len(hotels) * len(DATES)
    cash = sum(h['cells']['rates'] for h in hotels)
    pts = sum(h['cells']['points'] for h in hotels)
    full = all(h['cells']['rates'] > 0 and h['cells']['points'] > 0 for h in hotels)

    payload = {
        'group': 'ihg',
        'generated_at': date.today().isoformat(),
        'window': [DATES[0], DATES[-1]],
        'days': len(DATES),
        'hotels': hotels,
        'counts': {'hotels': len(hotels), 'cells': cells, 'cash': cash, 'points': pts},
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, separators=(',', ':'))

    print('wrote', OUT)
    print('hotels=%d cells=%d cash=%d points=%d' % (len(hotels), cells, cash, pts))
    by_reg = {}
    for h in hotels:
        by_reg[h['region']] = by_reg.get(h['region'], 0) + 1
    print('region', by_reg)
    print('brand', {k: sum(1 for h in hotels if h['brand_key'] == k) for k in sorted({h['brand_key'] for h in hotels})})
    print('qSHBrC', {k: sum(1 for h in hotels if h['brand_code'] == k) for k in sorted({h['brand_code'] for h in hotels})})
    if problems:
        print('PROBLEMS:', *problems, sep='\n  ')


if __name__ == '__main__':
    main()
