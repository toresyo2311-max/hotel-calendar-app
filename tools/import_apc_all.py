#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""② 중올플(APC) 전체 반영 — 부산 출발로 갈 수 있는 중국·홍콩·마카오 참여 호텔 274곳 편입.

원본: 수집 폴더의 availability.json (도시 128 + 호텔 490 · 참여 282 / 미참여 203 / 미확인 5)
      경로는 `APC_SRC` 환경변수로 지정한다(기본 /workspace/data-sources/apc-전체/availability.json).

규칙
  · ② 탭은 **참여 282곳 + 기존 10곳 중 참여가 아닌 2곳(AKI 홍콩·뫼벤픽 칭다오) = 284곳**.
  · 기존 10곳은 현금 요금(365일)을 그대로 두고 APC 상태만 public_id 로 다시 맞춘다.
  · 신규 274곳의 현금 요금은 수집하지 않았으므로 **추정하지 않고 365일 전부 null**.
    대신 `accor_apc`(날짜별 a/n) · `accor.dec`/`accor.nov`(관측·가능 일수) · 도시·브랜드·권역(tier)을 넣는다.
  · 상태 매핑: 원본 `A` → a(가능), `N` → n(불가), `B`/`X`(관측 72시간 초과)·행 없음 → 미확인(키 없음).
  · 출처 표기: 사이트 이름을 쓰지 않고 「예약 캘린더 관측 · 2026-11-16 기준」만 쓴다.

사용법 (저장소 루트에서):
    python3 tools/import_apc_all.py --dry
    python3 tools/import_apc_all.py
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER = os.path.join(ROOT, 'data', 'master_db.json')
SRC = os.environ.get('APC_SRC') or '/workspace/data-sources/apc-전체/availability.json'
REL = 'apc/부산출발-APC-전체-availability.json'
FRESH_HOURS = 72
WINDOW_START = '2026-12-01'
WINDOW_END = '2027-11-30'
DEC_WINDOW = ('2026-12-01', '2026-12-18')
NOV_WINDOW = ('2026-11-17', '2026-11-30')

# 기존 ② 탭 10곳 — id ↔ public_id (현금 요금 유지, APC 상태만 갱신)
LEGACY = {
    'c6480': 'public-93e12d415300',   # 소피텔 마카오 앳 폰테 16
    'cB5L5': 'public-92925991f976',   # AKI 홍콩 - 엠갤러리
    'c9933': 'public-a5c8ed3d9ac4',   # 소피텔 상하이 홍차오
    'cB628': 'public-5fe02dd7ad96',   # 소피텔 베이징 센트럴
    'c6318': 'public-78f75c38e7eb',   # 소피텔 광저우 선리치
    'c5554': 'public-4cb0b52085d9',   # 소피텔 항저우 웨스트레이크
    'c6179': 'public-5a4c62ae5728',   # 소피텔 난징 갤럭시 쑤닝
    'cC7G9': 'public-e204f247119e',   # 뫼벤픽 칭다오 5·4광장 (APC 자격 없음 → JSON 에 없음)
    'c6156': 'public-adfa93cabadd',   # 소피텔 레전드 피플스 그랜드 호텔 시안
    'cC2G5': 'public-7243cf9cec7c',   # 풀만 충칭 시위에
}
LEGACY_NAMES = {
    'c6480': '소피텔 마카오 앳 폰테 16',
    'cB5L5': 'AKI 홍콩 - 엠갤러리',
    'c9933': '소피텔 상하이 홍차오',
    'cB628': '소피텔 베이징 센트럴',
    'c6318': '소피텔 광저우 선리치',
    'c5554': '소피텔 항저우 웨스트레이크',
    'c6179': '소피텔 난징 갤럭시 쑤닝',
    'cC7G9': '뫼벤픽 칭다오 5·4광장',
    'c6156': '소피텔 레전드 피플스 그랜드 호텔 시안',
    'cC2G5': '풀만 충칭 시위에',
}

CITY_KR = {
    'cn-beijing': '베이징', 'cn-chengdu': '청두', 'cn-guangzhou': '광저우', 'cn-guilin': '구이린',
    'cn-hangzhou': '항저우', 'cn-harbin': '하얼빈', 'hk-hong-kong': '홍콩', 'cn-nanjing': '난징',
    'cn-qingdao': '칭다오', 'cn-shanghai': '상하이', 'cn-shenyang': '선양', 'cn-xian': '시안',
    'cn-xiamen': '샤먼', 'cn-zhangjiajie': '장자제', 'cn-baoding': '바오딩', 'cn-changsha': '창사',
    'cn-changshu': '창수', 'cn-changzhou': '창저우', 'cn-chaozhou': '차오저우', 'cn-chongqing': '충칭',
    'cn-danzhou': '단저우', 'cn-dongguan': '둥관', 'cn-foshan': '포산', 'cn-fuzhou': '푸저우',
    'cn-haikou': '하이커우', 'cn-handan': '한단', 'cn-hefei': '허페이', 'cn-huaian': '화이안',
    'cn-huizhou': '후이저우', 'cn-huzhou': '후저우', 'cn-jiangyin': '장인', 'cn-jiaxing': '자싱',
    'cn-jinan': '지난', 'cn-kaifeng': '카이펑', 'cn-kunming': '쿤밍', 'cn-kunshan': '쿤산',
    'cn-lianyungang': '롄윈강', 'cn-linyi': '린이', 'cn-luoyang': '뤄양', 'mo-macau': '마카오',
    'cn-nanchang': '난창', 'cn-nantong': '난퉁', 'cn-ningbo': '닝보', 'cn-pingyao': '핑야오',
    'cn-qidong': '치둥', 'cn-qinhuangdao': '친황다오', 'cn-quanzhou': '취안저우', 'cn-rizhao': '르자오',
    'cn-rugao': '루가오', 'cn-sanya': '싼야', 'cn-shaoxing': '사오싱', 'cn-shenzhen': '선전',
    'cn-shiyan': '스옌', 'cn-suzhou': '쑤저우', 'cn-taicang': '타이창', 'cn-taiyuan': '타이위안',
    'cn-taizhou': '타이저우', 'cn-taizhou-jiangsu': '타이저우(장쑤)', 'cn-tangshan': '탕산',
    'cn-tianjin': '톈진', 'cn-weifang': '웨이팡', 'cn-wenzhou': '원저우', 'cn-wuhan': '우한',
    'cn-wuxi': '우시', 'cn-xianyang': '셴양', 'cn-xinyang': '신양', 'cn-xuzhou': '쉬저우',
    'cn-yanan': '옌안', 'cn-yancheng': '옌청', 'cn-yangzhou': '양저우', 'cn-yichang': '이창',
    'cn-yixing': '이싱', 'cn-yueyang': '웨양', 'cn-zhengzhou': '정저우', 'cn-zhoushan': '저우산',
    'cn-zhuhai': '주하이', 'cn-anshun': '안순', 'cn-baishan': '바이산', 'cn-changchun': '창춘',
    'cn-dali': '다리', 'cn-datong': '다퉁', 'cn-enshi': '언스', 'cn-guiyang': '구이양',
    'cn-hohhot': '후허하오터', 'cn-jinghong': '징훙', 'cn-jiuzhaigou': '주자이거우',
    'cn-kashgarprefecture': '카슈가르', 'cn-lijiang': '리장', 'cn-linfen': '린펀', 'cn-mile': '미러',
    'cn-ordos': '어얼둬쓰', 'cn-tianshui': '톈수이', 'cn-urumqi': '우루무치', 'cn-xichang': '시창',
    'cn-xining': '시닝', 'cn-yangquan': '양취안', 'cn-yinchuan': '인촨', 'cn-yuncheng': '윈청',
    'cn-yuxi': '위시',
}

BRAND_KR = {
    'Mercure': '머큐어', 'Novotel': '노보텔', 'Pullman': '풀만', 'Grand Mercure': '그랜드 머큐어',
    'Sofitel': '소피텔', 'Sofitel Legend': '소피텔 레전드', 'Swissotel': '스위소텔', 'Swissôtel': '스위소텔',
    'MGallery': 'M갤러리', 'Fairmont': '페어몬트', 'ibis': '이비스', 'Movenpick': '뫼벤픽', 'Mövenpick': '뫼벤픽', 'Mövenpick': '뫼벤픽',
    'Handwritten Collection': '핸드라이튼 컬렉션', 'The Sebel': '더 세벨',
}

TIER_LABEL = {1: '김해 직항', 2: '환승·고속철 연계', 3: '국내선 환승 필요'}

# 브랜드·도시를 떼고 남은 영문 수식어 → 한글
DESC = {
    '': '',
    'Downtown': '다운타운', 'City Center': '시티센터', 'Railway Station': '역', 'Sunac': 'Sunac',
    'Central': '센트럴', 'Ancient City': '고성', 'East': '이스트', 'East Railway Station': '동역',
    'Airport': '공항', 'Hongqiao': '훙차오', 'South': '사우스', 'Hi-Tech District': '하이테크지구',
    'Baiyun Airport': '바이윈 공항', 'Exhibition Center': '전시센터', 'Yingguan': '잉관',
    'South Railway Station': '남역', 'Yalong Bay': '야룽베이', 'Qingpu Excellence': '칭푸 엑설런스',
    'Xiong An': '슝안', 'Advanced Business Park': '어드밴스트 비즈니스파크',
    'Capital International Airport': '서우두 국제공항', 'Chang An West': '창안 웨스트',
    'Chaoyang Panjiayuan': '차오양 판자위안', 'The Grand Canal CBD': '그랜드 캐널 CBD',
    'Universal Resort': '유니버설 리조트', 'Hong Kong Macau Center': '홍콩·마카오 센터',
    'Ziyou Road Dahua': '쯔유루 다화', 'Jingyue Xincheng': '징웨 신청',
    'International Exhibition Center': '국제전시센터', 'Leeman': '리먼', 'Luoxi': '뤄시',
    'Qingguo Lane': '칭궈루', 'Jintan': '진탄', 'Shuangliu International Airport': '솽류 국제공항',
    'Lige': '리거', 'Global Center': '글로벌 센터', 'Huapaifang': '화파이팡',
    'Tianfu Square': '톈푸 광장', 'Times Paradise Walk': '타임즈 파라다이스 워크',
    'Xiyue': '시웨', 'Yangpu Seaview': '양푸 씨뷰', 'Songshan Lake': '쑹산 호수', 'Changan': '창안',
    'Shunde': '순더', 'Tahoe': '타호', "Baiyun Int'l Airport": '바이윈 공항',
    'Baiyun International Airport': '바이윈 국제공항', 'Sunrich': '선리치',
    'Yangshuo Xingping': '양숴 싱핑', 'Hi Tech Zone': '하이테크지구', 'Hunter': '헌터',
    'Panjiang': '판장', 'West Coast': '웨스트 코스트', 'Xinbudao': '신부다오', 'Congtai': '총타이',
    'Qingshan Lake': '칭산 호수', 'Gongshu Wanda Plaza': '궁수 Wanda 플라자', 'Liping': '리핑',
    'Xixi Tianmu Mountain': '시시 톈무산', 'Yuhang': '위항', 'Binjiang Star Avenue': '빈장 스타 애비뉴',
    'Westlake': '웨스트레이크', 'West Lake': '웨스트레이크', 'Zijingang': '쯔진강', 'Daguan': '다관',
    'Wenyi Road': '원이루', 'Central Street Sophia Church': '센트럴 스트리트 소피아 성당',
    'City Hall Square': '시청 광장', 'Grand Park': '그랜드 파크',
    'Huhhot Economic Zone': '후허하오터 경제구', "Huai'an": '', 'Kaisa': '카이사',
    'South Taihu Lake': '사우스 타이후', 'Anji': '안지', 'South Gate Yaohan': '남문 야오한',
    'Port Area': '항구지구', 'Pinghu Excellence': '핑후 엑설런스', 'Sunshine': '선샤인',
    'HANYU FINANCIAL BUSINESS CENTRE': '한위 파이낸셜', 'North Down Town': '노스 다운타운',
    'Pingyin': '핑인', 'Xishuangbanna Tropical Botanical Garden': '시솽반나 열대식물원',
    'Jianye': '젠예', 'Kashgar Ancient City': '카슈가르 고성', 'Wujiaba': '우자바', 'Yunjin': '윈진',
    'Beimenlu': '베이먼루', 'MIXC Hi-tech': 'MIXC 하이테크', 'Yangcheng Lake': '양청 호수',
    'Haizhou': '하이저우', 'Suning': '쑤닝', 'Resort & Spa': '리조트&스파',
    'Resort Xishuangbanna': '시솽반나 리조트', 'Qingnian Avenue TV Tower': '칭녠대로 TV타워',
    'Renmin Square': '인민광장', 'on Renmin Square': '인민광장', 'Qujiang': '취장',
    'Dayan Pagoda': '대안탑', 'The Bell Tower': '종루',
    'Peoples Grand Hotel Xian': '피플스 그랜드 시안',
    'West Railway Station': '서역', 'Lushang': '루상', 'Hongden': '홍덴', 'Nanchang Road': '난창루',
    'Sun Yat-sen Mausoleum': '중산릉', 'Xuanwu Lake': '쉬안우 호수', 'East Suning': '이스트 쑤닝',
    'Lukou Airport': '루커우 공항', 'Galaxy Suning': '갤럭시 쑤닝', 'Olympic EXPO': '올림픽 엑스포',
    'Central Suning': '센트럴 쑤닝', 'Center': '센터', 'Development Zone': '개발구',
    'Suxitong Riverside': '쑤시퉁 강변', 'Yinzhou': '인저우', '(Opening Soon)': '(개관 예정)',
    'New Hope': '뉴호프', 'Shuitou': '수이토우', 'Haiqu': '하이취', 'One': '원',
    'Phoenix International Airport': '펑황 국제공항', 'Haitang Bay': '하이탕베이',
    'Oceanview Sanya Bay Resort & Spa': '오션뷰 싼야베이 리조트',
    'Leeman Resort': '리먼 리조트', 'Yalong Bay Villas & Resort': '야룽베이 빌라&리조트',
    'Hongqiao Airport': '훙차오 공항', 'Hongqiao South': '훙차오 사우스',
    'Waigaoqiao Free Trade Zone': '와이가오차오 자유무역지구', 'Wujiaochang': '우자오창',
    'Baoshan Jiusi': '바오산 지우쓰', 'Hongqiao Gubei': '훙차오 구베이', 'Xuhui': '쉬후이',
    'Baoshan': '바오산', 'Chuansha': '촨사', 'Lingang': '린강',
    'Lujiazui Binjiang Center': '루자쭈이 빈장 센터', 'Xujiahui': '쉬자후이', "Jing'an": '징안',
    'JingAn': '징안', 'Century Park': '센추리 파크', 'Hongqiao SOHO': '훙차오 SOHO',
    'Lingang Oriental Pearl': '린강 오리엔탈 펄', 'Lujiazui': '루자쭈이', 'NECC': 'NECC',
    'Pudong Zhangjiang Park': '푸둥 장장 파크', 'Clover': '클로버',
    'Hongqiao Railway Station': '훙차오 역', 'Xuhui Riverside': '쉬후이 리버사이드',
    'Suning Shanghai International Tourism Zone North Tower': '국제관광지 쑤닝 노스 타워',
    'Suning Shanghai International Tourism Zone South Tower': '국제관광지 쑤닝 사우스 타워',
    'North Bund': '베이쓰탄', 'Living Shanghai Hongqiao': '리빙 훙차오', 'Keqiao': '커차오',
    'Convention and Exhibition Center': '컨벤션·전시센터',
    'Qingnian Avenue TV Tower': '칭녠대로 TV타워', 'Nanshan': '난산', 'Pinghu': '핑후',
    'Watergate': '워터게이트', 'North': '노스', 'Dajia': '다자', 'HSR New Town': '고속철 신도시',
    'Changshu Yushan': '창수 위산', 'Huanxiu Lake': '환슈 호수', 'Zhonghui': '중후이',
    'SIP': 'SIP', 'Tai Lake Santeh': '타이후 산터', 'Changfeng Street': '창펑 스트리트',
    'Huahong (Opening Soon)': '화훙 (개관 예정)', 'Moganshan (Opening Soon)': '모간산 (개관 예정)', 'Tiantai': '톈타이', 'Shenxianju': '선셴쥐',
    'Taizhou Wanda Fengcheng River Scenic Area': 'Wanda 펑청허 관광지', 'Tanggu': '탕구',
    'Meijiang': '메이장', 'Hualing': '화링', 'Doowin Wanda Plaza': '두윈 Wanda 플라자',
    'Hanyang': '한양', 'Optics Valley': '옵틱스 밸리', 'Qiaokou': '차오커우', 'Yangluo': '양뤄',
    "Tian'an Intelligent Park": '톈안 인텔리전트 파크', 'Sanyang Plaza': '싼양 플라자',
    'New Lake': '뉴 레이크', 'Powerlong': '파워롱', 'On the Bund': '온더번드',
    'Science City': '사이언스 시티', 'Xian Renmin Square': '인민광장',
    'High-tech Zone Center': '하이테크존 센터', 'Stadium Hotel': '스타디움',
    'Xian Qujiang': '취장', 'Xian on Renmin Square': '인민광장', 'Xian Dayan Pagoda': '대안탑',
    'Xinxing': '신싱', 'Xian The Bell Tower': '종루', "Xi'an International Airport": '국제공항',
    'Xian Xixian': '시셴', "Qionghai Wetland": '충하이 습지', 'Tongshan': '퉁산',
    "Yan'an Downtown": '다운타운', 'High-Tech Zone': '하이테크존',
    'East High-Speed Railway Station': '동고속철역', 'Waitan': '와이탄', 'Huirong': '후이룽',
    'Lanxigu': '란시구', 'Xinhua': '신화', 'Wanda Plaza': 'Wanda 플라자',
    'Shanxi Yuncheng': '산시 윈청', 'International': '인터내셔널',
    'dong Railway Station Provincial Government': '동역',
    'North Point': '노스 포인트', 'Central & Sheung Wan': '센트럴·셩완', 'Citygate': '시티게이트',
    'Century Hong Kong': '센추리', 'at Ponte 16': '폰테 16',
}

# 브랜드+도시 규칙으로 풀리지 않는 이름은 여기서 직접 지정 (public_id → 한글 이름)
NAME_OVERRIDE = {
    'Swissôtel Resort Changbaishan': '스위소텔 창바이산 리조트',
    'The View Hotel Changbai Mountain - MGallery Collection': 'M갤러리 더 뷰 창바이산',
    'Chengdu Expo Waterfall Hotel - MGallery Collection': 'M갤러리 청두 엑스포 워터폴',
    'Financial City Hotel Chengdu-MGallery Collection (Opening Soon)': 'M갤러리 청두 파이낸셜 시티 (개관 예정)',
    'Ocean Spring Resort Chengdu - MGallery Collection': 'M갤러리 청두 오션 스프링 리조트',
    "DongFengYun Hotel Mi'Le - MGallery Collection": 'M갤러리 동펑윈 미러',
    'Fashion Town Hotel Shenzhen - MGallery Collection': 'M갤러리 선전 패션 타운',
    'Dangkou Ancient Town Hotel Wuxi - MGallery Collection': 'M갤러리 우시 당커우 고성',
    'Hotel Shanghai Hongqiao - Handwritten Collection': '핸드라이튼 컬렉션 상하이 훙차오',
    'The Silveri Hotel Hong Kong - MGallery Collection': 'M갤러리 더 실버리 홍콩',
    'THE SEBEL XI NING – Managed by Sofitel': '더 세벨 시닝',
    'Pullman Suzhou Taicang': '풀만 타이창',
    'Novotel Living Hangzhou International Convention Center': '노보텔 리빙 항저우 국제컨벤션센터',
    'Novotel Changshu Yushan': '노보텔 창수 위산',
}


def _load():
    with open(SRC, encoding='utf-8') as fp:
        return json.load(fp)


def _strip(name, city):
    """영문 호텔명에서 브랜드와 도시를 떼고 수식어만 남긴다."""
    s = name
    for b in sorted(BRAND_KR, key=len, reverse=True):
        if s.lower().startswith(b.lower()):
            s = s[len(b):].strip(' -–—')
            break
    for c in (city, city.replace("'", ''), city.replace("'", ' ')):
        if s.lower().startswith(c.lower()):
            s = s[len(c):].strip(' -–—')
            break
    s = s.replace('\u00a0', ' ').replace('  ', ' ')
    s = s.replace(' - MGallery Collection', '').replace('-MGallery Collection', '')
    s = s.replace(' - Handwritten Collection', '').replace(' – Managed by Sofitel', '')
    s = s.replace('(Opening Soon)', '(Opening Soon)')
    return s.strip()


def _dec_days(h):
    return h['months'].get('2026-12', {}).get('days', {})


def _nov_days(h):
    return h['months'].get('2026-11', {}).get('days', {})


CHECK_TZ = dt.timezone(dt.timedelta(hours=8))


def _iso_cn(s):
    """관측 사이트의 checked_at 은 중국 표준시 naive 문자열 → ISO(+08:00)."""
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=CHECK_TZ).isoformat()
    except ValueError:
        return s


def _window_counts(days, window):
    av = obs = 0
    for d, v in days.items():
        if not (window[0] <= d <= window[1]):
            continue
        if v == 'A':
            av += 1
            obs += 1
        elif v == 'N':
            obs += 1
        # B / X = 관측 72시간 초과 → 미확인으로 센다
    return {'available': av, 'observed': obs}


def _apc_map(days):
    out = {}
    for d, v in days.items():
        if not (WINDOW_START <= d <= WINDOW_END):
            continue
        if v == 'A':
            out[d] = 'a'
        elif v == 'N':
            out[d] = 'n'
    return dict(sorted(out.items()))


def build(data):
    cities = {c['city_key']: c for c in data['cities']}
    hotels = {h['public_id']: h for h in data['hotels']}
    months_checked = {}
    for h in data['hotels']:
        for mo, blk in h['months'].items():
            t = blk.get('checked_at')
            if t:
                months_checked.setdefault(mo, set()).add(t)

    rows = []
    missing_city = []
    unknown_desc = []
    for h in data['hotels']:
        if h['live_status']['participation_status'] != 'participating':
            continue
        c = cities[h['city_key']]
        kcity = CITY_KR.get(h['city_key'])
        if not kcity:
            missing_city.append(h['city_key'])
            kcity = c['name_en']
        desc = _strip(h['name_en'], c['name_en'])
        if h['name_en'] in NAME_OVERRIDE:
            kname = NAME_OVERRIDE[h['name_en']]
        elif desc in DESC:
            kname = (BRAND_KR.get(h['brand'], h['brand']) + ' ' + kcity +
                     (' ' + DESC[desc] if DESC[desc] else '')).strip()
        else:
            unknown_desc.append((h['public_id'], h['name_en'], desc))
            kname = BRAND_KR.get(h['brand'], h['brand']) + ' ' + kcity + ' ' + desc
        dec, nov = _dec_days(h), _nov_days(h)
        aprc = _apc_map(dec)
        newest = None
        for mo, blk in h['months'].items():
            t = blk.get('checked_at')
            if t and (newest is None or t > newest):
                newest = t
        rows.append({
            'public_id': h['public_id'],
            'name': kname,
            'english': h['name_en'],
            'brand': BRAND_KR.get(h['brand'], h['brand']),
            'brand_en': h['brand'],
            'city_key': h['city_key'],
            'city': kcity,
            'tier': c['tier'],
            'tier_label': c['tier_label'] or TIER_LABEL.get(c['tier'], ''),
            'apc': aprc,
            'apc_t': {dd: _iso_cn(h['months'][dd[:7]].get('checked_at')) for dd in aprc},
            'dec': _window_counts(dec, DEC_WINDOW),
            'nov': _window_counts(nov, NOV_WINDOW),
            'newest': _iso_cn(newest),
        })
    return rows, missing_city, unknown_desc


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args(argv)
    data = _load()
    rows, missing_city, unknown_desc = build(data)
    print('참여 호텔 %d곳 · 도시 %d개' % (len(rows), len({r['city_key'] for r in rows})))
    if missing_city:
        print('도시 한글명 없음(%d): %s' % (len(set(missing_city)), sorted(set(missing_city))))
    if unknown_desc:
        print('수식어 미번역(%d):' % len(unknown_desc))
        for pid, en, d in unknown_desc:
            print('   %s  %-55s  [%s]' % (pid, en, d))
    dec_ok = sum(1 for r in rows if r['dec']['available'])
    nov_ok = sum(1 for r in rows if r['nov']['available'])
    print('12월 1~18일 가능 1일 이상 %d곳 · 11월 17~30일 %d곳' % (dec_ok, nov_ok))
    print('APC 칸(12월 창) 합계 %d' % sum(len(r['apc']) for r in rows))
    print('권역 분포', {t: sum(1 for r in rows if r['tier'] == t) for t in (1, 2, 3)})
    if a.dry:
        return 0

    with open(MASTER, encoding='utf-8') as fp:
        master = json.load(fp)
    hotels = master['hotels']
    # 멱등: 이 스크립트가 앞서 넣은 ② 신규 호텔(ap###)은 지우고 다시 만든다
    hotels[:] = [h for h in hotels if not (h.get('group') == 'china' and
                                           h['id'] not in LEGACY and
                                           (h.get('accor') or {}).get('public_id'))]
    by_pid = {r['public_id']: r for r in rows}
    legacy_ids = set(LEGACY)
    catalog_pids = {x['public_id'] for x in data['hotels']}
    city_by_key = {c['city_key']: c for c in data['cities']}

    # 1) 기존 10곳 APC 상태 갱신 (현금 요금·약관 제외일 보존)
    used = set()
    for h in hotels:
        if h.get('group') != 'china' or h['id'] not in legacy_ids:
            continue
        pid = LEGACY[h['id']]
        cur = dict(h.get('accor') or {})
        r = by_pid.get(pid)
        if r:
            cur.update({
                'participation': 'participating',
                'required_nights': 1,
                'public_id': pid,
                'city_key': r['city_key'],
                'tier': r['tier'],
                'tier_label': r['tier_label'],
                'dec': r['dec'],
                'nov': r['nov'],
                'newest_checked': r['newest'],
                'fresh_hours': FRESH_HOURS,
            })
            h['accor_apc'] = r['apc']
            h['accor_apc_t'] = r['apc_t']
            used.add(pid)
        else:
            # 참여 목록에 없음: AKI 홍콩(미참여) · 뫼벤픽 칭다오(APC 자격 없음)
            cur['participation'] = 'not_participating'
            cur['eligible_catalog'] = pid in catalog_pids
            h['accor_apc'] = {}
            h['accor_apc_t'] = {}
            c = city_by_key.get(cur.get('city_key'))
            if c:
                cur['tier'] = c['tier']
                cur['tier_label'] = c['tier_label'] or TIER_LABEL.get(c['tier'], '')
                cur['dec'] = {'available': 0, 'observed': 0}
                cur['nov'] = {'available': 0, 'observed': 0}
        cur['source'] = '예약 캘린더 관측 · 2026-11-16 기준 (72시간 규칙)'
        cur['generated_at'] = data['generated_at']
        h['accor'] = {k: cur[k] for k in ('participation', 'required_nights', 'public_id',
                                          'city_key', 'source', 'generated_at',
                                          'newest_checked', 'fresh_hours') if k in cur}
        for k in ('tier', 'tier_label', 'dec', 'nov', 'eligible_catalog'):
            if k in cur:
                h['accor'][k] = cur[k]

    # 2) 신규 274곳 편입
    dates = []
    d0 = dt.date.fromisoformat(WINDOW_START)
    while d0.isoformat() <= WINDOW_END:
        dates.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    assert len(dates) == 365
    existing_ids = {h['id'] for h in hotels}
    new_rows = [r for r in rows if r['public_id'] not in used]
    new_rows.sort(key=lambda r: (r['tier'], r['city'], r['brand'], r['name']))
    seq = 0
    added = 0
    for r in new_rows:
        seq += 1
        hid = 'ap%03d' % seq
        while hid in existing_ids:
            seq += 1
            hid = 'ap%03d' % seq
        existing_ids.add(hid)
        hotels.append({
            'id': hid,
            'group': 'china',
            'city': r['city'],
            'name': r['name'],
            'english': r['english'],
            'brand': r['brand'],
            'promotion': '',
            'rates': {d: None for d in dates},
            'source': '예약 캘린더 관측(APC 무료숙박 가능일) · 2026-11-16 / 현금 요금 미수집',
            'accor': {
                'participation': 'participating',
                'required_nights': 1,
                'public_id': r['public_id'],
                'city_key': r['city_key'],
                'tier': r['tier'],
                'tier_label': r['tier_label'],
                'dec': r['dec'],
                'nov': r['nov'],
                'source': '예약 캘린더 관측 · 2026-11-16 기준 (72시간 규칙)',
                'generated_at': data['generated_at'],
                'newest_checked': r['newest'],
                'fresh_hours': FRESH_HOURS,
            },
            'accor_apc': r['apc'],
            'accor_apc_t': r['apc_t'],
        })
        added += 1

    master['sources'] = [s for s in master.get('sources', []) if s != REL] + [REL]
    tag = '2026-11-17 ② 중올플 284곳(참여 282 + 기존 2) · 99개 도시 · 권역(tier) 필터'
    ext = master.get('extended') or ''
    if '중올플 284곳' not in ext:
        master['extended'] = (ext + ' / ' + tag).strip(' /')
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import master_db  # noqa: E402
    st = master_db.stats_of(master, master['flights'])
    master['counts'] = {k: st[k] for k in ('hotels', 'tabs', 'cells', 'priced', 'na',
                                           'stayplus', 'routes', 'deals')}
    with open(MASTER, 'w', encoding='utf-8') as fp:
        json.dump(master, fp, ensure_ascii=False, indent=1)
        fp.write('\n')
    print('counts', json.dumps(master['counts'], ensure_ascii=False))
    print('master_db.json 갱신 — ② 중올플 %d곳 (기존 10 + 신규 %d)' % (10 + added, added))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
