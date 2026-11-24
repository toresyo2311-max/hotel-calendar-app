#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-11-25 새벽 정기 갱신 — ② 중국(APC) 무료숙박 가능일 + ③ 국내 아코르 1박 최저가.

입력 (워크스페이스 `work/accor-daily/`):
  · apc_availability_20261125.json — 예약 캘린더 공개 API 도시별 조회(2026-11-25~2026-12-18, benefit=zhenxiang) — 관측 일수 24일
  · kr_all_20261125.json          — all.accor.com GraphQL 달력 조회(국내 30곳 × 365일, 8일 창)

하는 일
  · 중국(APC) 289곳: 참여 상태·필요 숙박일수를 공개 API 값으로 맞추고,
    `accor_apc`/`accor_apc_t` 를 2026-12-01~12-18 관측값으로 **통째로 교체**한다
    (관측이 없는 날짜는 키를 두지 않아 화면에서 '미확인'으로 보인다).
    `accor.dec`(12/1~12/18)·`accor.nov`(11/17~11/30) 관측/가능 일수와
    `source`·`newest_checked`·`generated_at` 도 함께 갱신한다.
  · 국내 아코르 30곳: 달력 조회값(세금 포함 총액)에서 부가세 10%를 뺀 **세금 제외 회원 최저가**로
    `rates` 365일을 교체한다(판매 없음은 null). 화면 표기 기준(세금 별도)과 같다.

사용법: python3 tools/merge_accor_daily_20261124.py [--dry]
"""
import argparse
import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
DAILY = os.path.join(os.path.dirname(ROOT), 'work', 'accor-daily')
SRC_APC = os.path.join(DAILY, 'apc_availability_20261125.json')
SRC_KR = os.path.join(DAILY, 'kr_all_20261125.json')

DEC_WINDOW = ('2026-12-01', '2026-12-18')
NOV_WINDOW = ('2026-11-17', '2026-11-30')
TODAY = '2026-11-25'
CN_TZ = dt.timezone(dt.timedelta(hours=8))
VAT = 1.1   # 대한민국 부가세 10% — 화면은 세금 제외가로 적는다(총액 ÷ 1.1)


def iso_cn(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=CN_TZ).isoformat()
    except ValueError:
        return s


def load_apc():
    with open(SRC_APC, encoding='utf-8') as fp:
        d = json.load(fp)
    avail = {}      # public_id -> {date: ('a'/'n', iso_ts)}
    benefit = {}    # public_id -> zhenxiang benefit row
    for city in d['cities'].values():
        for a in city['availability']:
            st = 'a' if a['status'] == 'available' else 'n'
            avail.setdefault(a['public_id'], {})[a['checkin_date']] = (st, iso_cn(a['last_checked_at']))
        for b in city['hotel_benefits']:
            if b['benefit_type'] == 'zhenxiang':
                benefit[b['public_id']] = b
    return avail, benefit, d


def window_counts(days, window):
    a = o = 0
    for d, (st, _t) in days.items():
        if not (window[0] <= d <= window[1]):
            continue
        if st == 'a':
            a += 1
            o += 1
        elif st == 'n':
            o += 1
    return {'available': a, 'observed': o}


def merge_apc(master, dry):
    avail, benefit, src = load_apc()
    now = dt.datetime.now(CN_TZ).isoformat(timespec='seconds')
    stat = {'hotels': 0, 'a_to_n': 0, 'n_to_a': 0, 'new': 0, 'dropped': 0,
            'no_fresh': 0, 'participation_changed': 0, 'unmatched': 0}
    newest_all = None
    for h in master['hotels']:
        a = h.get('accor')
        if h.get('zone') != 'cn' or not a:
            continue
        pid = a.get('public_id')
        if pid not in avail:
            stat['unmatched'] += 1
            continue
        days = avail[pid]
        dec = {d: v for d, v in days.items() if DEC_WINDOW[0] <= d <= DEC_WINDOW[1]}
        if not dec:
            stat['no_fresh'] += 1
            continue
        old = h.get('accor_apc') or {}
        for d, (st, _t) in dec.items():
            o = old.get(d)
            if o is None:
                stat['new'] += 1
            elif o != st:
                stat['a_to_n' if (o, st) == ('a', 'n') else 'n_to_a'] += 1
        stat['dropped'] += sum(1 for d in old if d not in dec)
        h['accor_apc'] = dict(sorted((d, v[0]) for d, v in dec.items()))
        h['accor_apc_t'] = dict(sorted((d, v[1]) for d, v in dec.items()))
        a['dec'] = window_counts(days, DEC_WINDOW)
        a['nov'] = window_counts(days, NOV_WINDOW)
        b = benefit.get(pid)
        if b:
            if a.get('participation') != b['participation_status']:
                stat['participation_changed'] += 1
            a['participation'] = b['participation_status']
            if b.get('required_nights'):
                a['required_nights'] = b['required_nights']
        newest = max(v[1] for v in dec.values())
        newest_all = max(newest_all, newest) if newest_all else newest
        a['source'] = '예약 캘린더 관측 · %s 기준 (72시간 규칙)' % TODAY
        a['newest_checked'] = newest
        a['generated_at'] = now
        a['fresh_hours'] = 72
        stat['hotels'] += 1
    print('② 중국(APC) 갱신 %d곳 · 신규 %d · 가능→불가 %d · 불가→가능 %d · 이번 관측에 없어 제거 %d'
          ' · 12월 관측 없는 호텔 %d · 공개 API 매칭 실패 %d · 참여상태 변경 %d'
          % (stat['hotels'], stat['new'], stat['a_to_n'], stat['n_to_a'], stat['dropped'],
             stat['no_fresh'], stat['unmatched'], stat['participation_changed']))
    print('   최신 관측 시각 %s (관측 %d개 도시 · %d건)'
          % (newest_all, len(src['cities']), sum(len(c['availability']) for c in src['cities'].values())))
    return stat


def merge_kr(master, dry):
    with open(SRC_KR, encoding='utf-8') as fp:
        data = json.load(fp)
    stat = {'hotels': 0, 'cells': 0, 'changed': 0, 'to_null': 0, 'from_null': 0, 'same': 0, 'outlier': 0}
    for h in master['hotels']:
        if h.get('zone') != 'kr':
            continue
        rec = data.get(h.get('code'))
        if not rec:
            print('  ! 국내 수집값 없음', h['id'], h['name'])
            continue
        rates = h.get('rates') or {}
        # 이상값 규칙 — 달력이 1박이 아닌 상품(레지던스·객실 이용 가능 보장 등)을 돌려주는 날이 있어,
        #   1천만 원 초과 또는 그 호텔 연중 중앙값의 4배를 넘는 값은 가격으로 쓰지 않고 null 로 둔다.
        got = [round(v['min'] / VAT) for v in rec['days'].values()
               if v.get('min') and v.get('status') == 'AVAILABLE']
        med = sorted(got)[len(got) // 2] if got else 0
        for d, v in rec['days'].items():
            old = rates.get(d)
            new = round(v['min'] / VAT) if (v.get('min') and v.get('status') == 'AVAILABLE') else None
            if new is not None and (new > 10_000_000 or (med and new > med * 4)):
                new = None
                stat['outlier'] += 1
            if new is None and old is None:
                stat['same'] += 1
            elif new is None:
                stat['to_null'] += 1
            elif old is None:
                stat['from_null'] += 1
            elif new == old:
                stat['same'] += 1
            else:
                stat['changed'] += 1
            rates[d] = new
        h['rates'] = dict(sorted(rates.items()))
        h['source'] = '국내 아코르 전 지점 365일 조회(%s) — all.accor.com 날짜별 요금보기(회원 최저가·세금 제외)' % TODAY
        stat['hotels'] += 1
        stat['cells'] += len(rec['days'])
    print('③ 국내 아코르 %d곳 · %d칸 · 값 변경 %d · 신규 %d · 판매없음 전환 %d · 동일 %d · 이상값 제외 %d'
          % (stat['hotels'], stat['cells'], stat['changed'], stat['from_null'], stat['to_null'],
             stat['same'], stat['outlier']))
    return stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    apc = merge_apc(master, a.dry)
    kr = merge_kr(master, a.dry)

    srcs = list(master.get('sources') or [])
    for s in ('예약 캘린더 관측 2026-11-25 — 중국 APC 도시 101개 · 2026-11-25~12-18 (A/N)',
              'all.accor.com 회원 최저가 달력 조회 2026-11-25 — 국내 30곳 × 365일(세금 제외)'):
        if s not in srcs:
            srcs.append(s)
    master['sources'] = srcs
    master['extended'] = (master.get('extended') or '') + (
        ' / 2026-11-25 새벽 정기 갱신 — ② 중국(APC) 289곳 무료숙박 가능일 재관측(%d곳 갱신 · 가능→불가 %d · 불가→가능 %d)'
        ' + ③ 국내 아코르 30곳 365일 회원 최저가 재조회(값 변경 %d칸, 세금 제외 기준)'
        % (apc['hotels'], apc['a_to_n'], apc['n_to_a'], kr['changed']))
    master['generated_at'] = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='seconds')

    if a.dry:
        print('(dry) 저장 생략')
        return
    tmp = MASTER + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    os.replace(tmp, MASTER)
    print('saved', MASTER)


if __name__ == '__main__':
    main()
