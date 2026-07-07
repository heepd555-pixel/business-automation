"""
full_universe.py -- KIS 랭킹 API로 "전체 종목"에 가까운 유니버스를 동적으로 구성 (신규 파일)

[ 왜 필요한가 ]
예전 universe.py 는 config.py 에 사람이 직접 적어둔 66개 고정 종목만 봤습니다.
"전체 종목으로 봐줘" 라는 요청에 맞춰, 실행할 때마다 KIS API 로 시가총액 상위
종목을 직접 조회해서 유니버스를 구성하도록 확장했습니다.

[ 국내(KR) -- 왜 "진짜 전체 2500여개"가 아닌가 ]
KIS의 "시가총액 상위" 랭킹 API(FHPST01740000)는 한 번 호출에 최대 30건만 주고
"다음 페이지" 조회를 지원하지 않습니다 (공식 문서에 명시된 제약).
그래서 가격대(0~5천원, 5천~1만원, ... )를 나눠 KOSPI/KOSDAQ 각각 여러 번 호출한 뒤
종목코드를 중복 제거해서 모읍니다. 결과적으로 코스피/코스닥 시가총액 상위 다수
(보통 300~500개 내외, 거래대금이 있는 대부분의 유의미한 종목)를 커버하지만,
거래가 거의 없는 초소형주까지 전부 포함하는 건 아닙니다.
(참고: pykrx 로 진짜 전체 종목 리스트를 시도했으나 이 환경에서 KRX 데이터 서버
 응답이 깨져서 동작하지 않아, 안정적으로 동작하는 KIS API 랭킹 방식을 택했습니다.)

[ 해외(미국 등) ]
KIS의 "해외주식 시가총액순위" API(HHDFS76350100)는 한 번에 최대 100건을 주므로
가격대 분할 없이 거래소(나스닥/뉴욕/아멕스)별 상위 100개씩만 가져옵니다.
"""
import logging
import time

logger = logging.getLogger(__name__)

# 국내 가격대 구간 (원) -- 30건 제한을 넘어서기 위한 분할 기준
# 필요하면 구간을 더 촘촘히 나눠도 되지만, 그만큼 API 호출 수가 늘어남
KR_PRICE_BANDS = [
    ("", "5000"),
    ("5001", "10000"),
    ("10001", "20000"),
    ("20001", "50000"),
    ("50001", "100000"),
    ("100001", "300000"),
    ("300001", ""),
]

# 국내 시장 구분 코드 (kis_api.get_market_cap_ranking 의 market_code 인자)
KR_MARKETS = {
    "코스피": "0001",
    "코스닥": "1001",
}

# 미국 거래소 코드 (kis_api.get_overseas_market_cap_ranking 의 excd 인자)
US_EXCHANGES = {
    "나스닥": "NAS",
    "뉴욕":   "NYS",
    "아멕스": "AMS",
}


def fetch_kr_universe(api, price_bands: list = None, on_progress=None) -> list:
    """
    KOSPI + KOSDAQ 시가총액 상위 종목을 가격대별로 나눠 조회 + 중복 제거.

    Returns: [{"code","name","market_cap"}, ...] 시가총액 내림차순
    """
    bands = price_bands or KR_PRICE_BANDS
    seen  = {}   # code -> row (중복 제거, 먼저 본 것 유지)

    calls = [(mname, mcode, p1, p2) for mname, mcode in KR_MARKETS.items() for p1, p2 in bands]
    for i, (mname, mcode, p1, p2) in enumerate(calls, start=1):
        if on_progress:
            on_progress(i, len(calls), f"{mname} {p1 or '0'}~{p2 or '무제한'}원")
        rows = api.get_market_cap_ranking(mcode, price_min=p1, price_max=p2)
        for row in rows:
            code = row["code"]
            if code and code not in seen:
                seen[code] = row
        time.sleep(0.15)

    universe = sorted(seen.values(), key=lambda r: r["market_cap"], reverse=True)
    logger.info(f"[full_universe] 국내 유니버스 구성 완료: {len(universe)}종목")
    return universe


def fetch_us_universe(api, exchanges: dict = None, on_progress=None) -> list:
    """
    미국(나스닥/뉴욕/아멕스) 시가총액 상위 100개씩 조회 + 중복 제거.

    Returns: [{"code","name","market_cap","excd"}, ...] 시가총액 내림차순
    """
    excs = exchanges or US_EXCHANGES
    seen = {}

    for i, (ename, ecode) in enumerate(excs.items(), start=1):
        if on_progress:
            on_progress(i, len(excs), ename)
        rows = api.get_overseas_market_cap_ranking(ecode)
        for row in rows:
            code = row["code"]
            if code and code not in seen:
                row["excd"] = ecode
                seen[code] = row
        time.sleep(0.15)

    universe = sorted(seen.values(), key=lambda r: r["market_cap"], reverse=True)
    logger.info(f"[full_universe] 미국 유니버스 구성 완료: {len(universe)}종목")
    return universe
