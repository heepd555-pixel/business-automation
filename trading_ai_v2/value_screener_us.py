"""
value_screener_us.py -- 미국 주식용 저평가 우량주 스크리너 (신규 파일)

[ KR 버전(value_screener.py)과 다른 점 ]
KIS API 는 국내 주식과 달리 미국 주식의 대차대조표·손익계산서·부채비율·
성장률을 제공하지 않습니다 (해외주식 현재가상세 API 에는 PER/PBR/EPS/BPS 만 있음).
그래서 이 파일은:
  - ROE 를 "EPS ÷ BPS × 100" 으로 근사 계산합니다.
    (실제 ROE = 당기순이익/자기자본. EPS=순이익/주식수, BPS=자기자본/주식수 이므로
     EPS/BPS = 순이익/자기자본 = ROE 와 수학적으로 동일합니다. 다만 분기/연간
     기준이 매끄럽게 안 맞을 수 있어 "근사치"로 취급합니다.)
  - 부채비율, 매출성장률 필터는 데이터가 없어서 적용하지 않습니다 (건너뜀).
  - 종합점수 = 저평가점수 × 0.5 + 우량점수(근사 ROE) × 0.5
    (KR 버전보다 필터가 느슨한 대신 참고용으로만 활용해야 함을 README 에 명시)
"""
import logging
import time

from config import SCREENER

logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _value_score(per: float, pbr: float) -> float:
    per_score = _clamp((SCREENER.PER_MAX - per) / SCREENER.PER_MAX * 100) if per > 0 else 50.0
    pbr_score = _clamp((SCREENER.PBR_MAX - pbr) / SCREENER.PBR_MAX * 100) if pbr > 0 else 50.0
    return (per_score + pbr_score) / 2


def _quality_score(roe: float) -> float:
    return _clamp(roe / 30.0 * 100)


# ETF/신탁(트러스트)/펀드 이름에 흔히 들어가는 키워드.
# 이런 종목은 "회사"가 아니라 금·은·비트코인 등을 수동으로 보유만 하는 투자상품이라
# PER/EPS/BPS/ROE 같은 기업 재무지표 자체가 의미가 없습니다 (그런데도 KIS 데이터에
# 0이 아닌 값이 찍혀서 필터를 통과하는 경우가 있어 이름으로 별도 제외합니다).
_FUND_KEYWORDS = (
    "ETF", "TRUST", "FUND", "ISHARES", "VANGUARD", "SPDR", "INVESCO",
    "PROSHARES", "GRAYSCALE", "SPROTT", "VANECK", "WISDOMTREE", "SCHWAB US",
    "DIREXION", "GLOBAL X", "FIRST TRUST", "SELECT SECTOR", "DIMENSIONAL",
    "CAPITAL GROUP", "JPMORGAN EQUITY PREMIUM", "AVANTIS",
    "트러스트", "펀드",   # KIS 가 드물게 한글명을 주는 경우 대비 (신탁/펀드)
)


def _is_fund_or_trust(name: str) -> bool:
    upper = name.upper()
    return any(kw in upper for kw in _FUND_KEYWORDS)


def fetch_us_metrics(row: dict, api) -> dict:
    """
    full_universe.fetch_us_universe() 가 준 종목 하나(row)에 대해
    KIS 해외주식 현재가상세로 PER/PBR/EPS/BPS 를 조회.
    """
    detail = api.get_overseas_price_detail(row["excd"], row["code"])
    price  = detail["price"] or row.get("price", 0.0)
    eps, bps = detail["eps"], detail["bps"]
    approx_roe = (eps / bps * 100) if bps > 0 else 0.0

    return {
        "code":       row["code"],
        "name":       row.get("name", row["code"]),
        "excd":       row["excd"],
        "price":      price,
        "per":        detail["per"],
        "pbr":        detail["pbr"],
        "eps":        eps,
        "bps":        bps,
        "roe":        round(approx_roe, 2),   # 근사치 (EPS/BPS)
    }


def evaluate_us(metrics: dict) -> dict:
    """
    KR 버전의 evaluate() 와 대응되는 함수. 부채비율/성장률/순이익 필터는 없음.

    [ v2 -- 페니스톡/부실기업 오탐 수정 ]
    유니버스를 거래대금순위 기반으로 확장한 뒤, 초저가 페니스톡과 PER 이 거의
    0에 가까운(예: 0.01배) 종목이 "데이터 이상치"인데도 필터를 통과해 상위권을
    휩쓰는 문제가 발견됐습니다. 예를 들어 주가 1달러 미만, 자기자본이 0에 가까운
    회사는 EPS/BPS 근사 ROE 가 수백~수천 %로 튀어서 "우량주"로 오판됩니다.
    KR 스크리너는 당기순이익 흑자 여부로 이런 부실기업을 걸러내지만, 미국은 그
    데이터가 없어서 대신 (1) 주가가 US_MIN_PRICE(기본 $5) 미만인 페니스톡 제외,
    (2) PER 이 PER_MIN(기본 1.0배) 미만인 종목 제외(0 이거나 데이터 이상치일 확률 높음),
    (3) PBR·BPS 가 0 이하인 종목 제외로 방어합니다.
    (4) 이름에 ETF/TRUST/FUND 등이 들어간 투자상품은 "기업"이 아니므로 이름으로 제외.
    """
    per, pbr, roe, price = metrics["per"], metrics["pbr"], metrics["roe"], metrics["price"]
    bps = metrics["bps"]
    reasons = []
    passes  = True

    if price <= 0:
        return {
            **metrics,
            "passes_filter": False,
            "value_score": 0.0, "quality_score": 0.0, "score": 0.0,
            "reasons": ["현재가/재무데이터 조회 실패"],
        }

    if _is_fund_or_trust(metrics["name"]):
        return {
            **metrics,
            "passes_filter": False,
            "value_score": 0.0, "quality_score": 0.0, "score": 0.0,
            "reasons": ["ETF/신탁/펀드 -- 개별 기업이 아니라 재무지표 평가 대상 아님"],
        }

    if price < SCREENER.US_MIN_PRICE:
        passes = False
        reasons.append(f"주가 ${price:.2f} -- 페니스톡 기준(${SCREENER.US_MIN_PRICE}) 미만이라 제외")

    # PER 이 PER_MIN 미만(0 포함)이면 적자이거나 데이터 이상치일 확률이 높아 제외.
    # "모른다"로 관대하게 통과시키지 않고 확실히 걸러냅니다 (부실주 오탐 방지).
    if per < SCREENER.PER_MIN:
        passes = False
        reasons.append(f"PER {per:.2f}배로 기준({SCREENER.PER_MIN}배) 미만 -- 적자/데이터 이상치 가능성")
    elif per > SCREENER.PER_MAX:
        passes = False
        reasons.append(f"PER {per:.1f}배로 기준({SCREENER.PER_MAX}배) 초과 -> 고평가")

    if pbr <= 0:
        passes = False
        reasons.append("PBR 0 이하 -- 데이터 없음 (부실주 가능성)")
    elif pbr > SCREENER.PBR_MAX:
        passes = False
        reasons.append(f"PBR {pbr:.2f}배로 기준({SCREENER.PBR_MAX}배) 초과 -> 고평가")

    if bps <= 0:
        passes = False
        reasons.append("BPS 0 이하 -- 자기자본 데이터 없음/훼손 (ROE 근사 신뢰 불가)")

    if roe < SCREENER.ROE_MIN:
        passes = False
        reasons.append(f"ROE(근사치) {roe:.1f}%로 기준({SCREENER.ROE_MIN}%) 미달")

    value_score   = _value_score(per, pbr)
    quality_score = _quality_score(roe)
    total_score   = round(value_score * 0.5 + quality_score * 0.5, 1)

    if passes:
        reasons.insert(0, (
            f"PER {per:.1f}배 / PBR {pbr:.2f}배 (저평가), "
            f"ROE(근사치) {roe:.1f}% (우량) -- 부채비율/성장률은 미국 주식 데이터 미제공으로 미반영"
        ))

    return {
        **metrics,
        "passes_filter": passes,
        "value_score":   round(value_score, 1),
        "quality_score": round(quality_score, 1),
        "score":         total_score,
        "reasons":       reasons,
    }


def rank_us_universe(rows: list, api, top_n: int = None, on_progress=None) -> list:
    """full_universe.fetch_us_universe() 결과를 받아 평가 + 순위 매기기."""
    results = []
    total = len(rows)
    for i, row in enumerate(rows, start=1):
        if on_progress:
            on_progress(i, total, f"{row['name']}({row['code']})")
        try:
            metrics = fetch_us_metrics(row, api)
            results.append(evaluate_us(metrics))
        except Exception as e:
            logger.warning(f"[value_screener_us] {row.get('code')} 평가 실패: {e}")
        time.sleep(0.15)

    passed = [r for r in results if r["passes_filter"]]
    passed.sort(key=lambda r: r["score"], reverse=True)
    return passed[:top_n] if top_n else passed
