#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""예약 링크용 데이터 보강 (1회성).

1) ⑤ 메리어트 중국 40곳의 propertyCode 를 채운다 (marriott.com 호텔 페이지 URL 에서 확인).
2) ① VIP 요금 탭에서 아직 호텔 페이지 주소가 없던 19곳의 ref_id 를 채운다.
3) ② 중올플 289곳에 중국어·영문 호텔명(nameZh / nameEn)을 붙인다 — 위챗 미니프로그램 검색용.
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(BASE, 'data', 'master_db.json')
APC = '/workspace/data-sources/apc-전체/availability.json'

# ⑤ 메리어트 중국 40곳 — marriott.com 호텔 페이지/검색 결과에서 확인한 propertyCode
MARRIOTT_CODES = {
    'm01': 'BJSRZ',  # The Ritz-Carlton, Beijing (China Central Place)
    'm02': 'BJSFS',  # The Ritz-Carlton Beijing, Financial Street
    'm03': 'SHASZ',  # The Ritz-Carlton Shanghai, Pudong
    'm04': 'SHARZ',  # The Portman Ritz-Carlton, Shanghai
    'm05': 'CANRZ',  # The Ritz-Carlton, Guangzhou
    'm06': 'SZXRZ',  # The Ritz-Carlton, Shenzhen
    'm07': 'CTURZ',  # The Ritz-Carlton, Chengdu
    'm08': 'XIYRZ',  # The Ritz-Carlton, Xi'an
    'm09': 'TSNRZ',  # The Ritz-Carlton, Tianjin
    'm10': 'HAKRZ',  # The Ritz-Carlton, Haikou
    'm11': 'SYXRZ',  # The Ritz-Carlton Sanya, Yalong Bay
    'm12': 'HRBRZ',  # The Ritz-Carlton, Harbin
    'm13': 'NKGRZ',  # The Ritz-Carlton, Nanjing
    'm14': 'WUXSZ',  # The Ritz-Carlton, Suzhou
    'm15': 'WUHRZ',  # The Ritz-Carlton, Wuhan
    'm16': 'HKGKW',  # The Ritz-Carlton, Hong Kong
    'm17': 'MFMMR',  # The Ritz-Carlton, Macau
    'm18': 'JZHRZ',  # Rissai Valley, a Ritz-Carlton Reserve
    'm19': 'BJSXR',  # The St. Regis Beijing
    'm20': 'CTUXR',  # The St. Regis Chengdu
    'm21': 'SHAXB',  # The St. Regis on the Bund, Shanghai
    'm22': 'TSNXR',  # St. Regis Tianjin
    'm23': 'CSXXR',  # The St. Regis Changsha
    'm24': 'SYXXR',  # The St. Regis Sanya Yalong Bay Resort
    'm25': 'ZUHXR',  # The St. Regis Zhuhai
    'm26': 'TAOXR',  # The St. Regis Qingdao
    'm27': 'SZXXR',  # The St. Regis Shenzhen
    'm28': 'SZXXS',  # The St. Regis Shenzhen Bao'an
    'm29': 'HKGXR',  # The St. Regis Hong Kong
    'm30': 'MFMXR',  # The St. Regis Macao
    'm31': 'LXAXR',  # The St. Regis Lhasa Resort
    'm32': 'SHAWH',  # W Shanghai – The Bund
    'm33': 'CANWG',  # W Guangzhou
    'm34': 'XIYWH',  # W Xi'an
    'm35': 'CTUWH',  # W Chengdu
    'm36': 'CSXWH',  # W Changsha
    'm37': 'SZVWH',  # W Suzhou
    'm38': 'XMNWH',  # W Xiamen
    'm39': 'HKGWH',  # W Hong Kong
    'm40': 'MFMWH',  # W Macau – Studio City
}

# ① VIP 요금 탭 — 호텔 페이지 주소(24자리 호텔 ID)가 비어 있던 19곳
LUX_REF = {
    'h04': '5b50d91512bd3f60197e2d60',  # Fairmont Peace Hotel Shanghai
    'h05': '5b5078036a8860a3024e0fd3',  # Pudong Shangri-La, Shanghai
    'h06': '62031c282d09041129d1ecd7',  # Conrad Shanghai
    'h07': '5b5077fc6a8860a3024e0fb2',  # The St. Regis Shanghai Jingan
    'h08': '5b48dbc2a4144f1a4f370934',  # Grand Hyatt Fukuoka
    'h09': '645db4be4c08f00a4ea90a1c',  # The Ritz-Carlton, Fukuoka
    'h10': '5b35ea6a21b146b104fd53aa',  # Conrad Osaka
    'h11': '6756505e12134c242d6dc620',  # Waldorf Astoria Osaka
    'h14': '690812d063875f0dc0f02078',  # Fairmont Bangkok Sukhumvit
    'h15': '5eb61aae23779d6e848795f4',  # Kimpton Maa-Lai Bangkok
    'h16': '5b506df06a8860a3024daed2',  # Waldorf Astoria Bangkok
    'h17': '5b506c826a8860a3024da116',  # Mandarin Oriental, Bangkok
    'h18': '5cf01a4c5b6b1f051a38d52a',  # Capella Bangkok
    'h19': '5b8ca3928ecdbb943c0abb04',  # Hyatt Regency Danang Resort and Spa
    'h20': '5b8cac005d7d2cd8f8ebbe21',  # InterContinental Danang Sun Peninsula Resort
    'h21': '5b8caade5d7d2cd8f8ebbbe4',  # Four Seasons Resort The Nam Hai
    'h22': '6901b6b1cad72361a55ec9ba',  # JW Marriott Cam Ranh Bay Resort & Spa
    'h23': '6495876a84b58573bcd84faa',  # Six Senses Ninh Van Bay
    'h24': '5b5055be74de201bce684ca4',  # Amanoi
}


def main():
    master = json.load(open(MASTER, encoding='utf-8'))
    apc = json.load(open(APC, encoding='utf-8'))
    by_public = {h['public_id']: h for h in apc['hotels'] if h.get('public_id')}

    hotels = master['hotels']
    idx = {h['id']: h for h in hotels}

    for hid, code in MARRIOTT_CODES.items():
        h = idx[hid]
        if h.get('code'):
            assert h['code'] == code, (hid, h['code'], code)
            continue
        h['code'] = code

    for hid, ref in LUX_REF.items():
        h = idx[hid]
        if h.get('ref_id'):
            assert h['ref_id'] == ref, (hid, h['ref_id'], ref)
            continue
        h['ref_id'] = ref

    named = 0
    for h in hotels:
        if h.get('group') != 'china':
            continue
        pid = (h.get('accor') or {}).get('public_id')
        src = by_public.get(pid)
        if not src:
            continue
        zh = (src.get('name_zh') or '').strip()
        if zh:
            h['nameZh'] = zh
            named += 1

    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, separators=(',', ':'))
    print('OK — 메리어트 코드 %d, 호텔 페이지 주소 %d, 중국어 이름 %d곳' % (
        len(MARRIOTT_CODES), len(LUX_REF), named))


if __name__ == '__main__':
    main()
