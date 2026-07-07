"""
value_screener.py -- 저평가 우량주 스크리너 (신규 파일)

[ 이 파일이 하는 일 ]
예전 financial_filter.py 는 "재무가 나쁜 종목을 매매 후보에서 제외"하는
용도였습니다 (매매 프로그램의 부품 중 하나). 이 파일은 그 역할을 완전히
새로 만든 것으로, 목적 자체가 다릅니다:

    "지금 가진 종목 목록 중에서, 재무제표(대차대조표·손익계산서)를 기준으로
     '좋은 회사인데 주가는 싼' 종목을 찾아서 점수를 매기고 순위를 매긴다."

[ v2 변경사항 -- 추가 지표 4종 반영 ]
  - [추가] PEG 비율 (PER ÷ 영업이익증가율) -- "저평가"와 "성장"을 함께 보는 지표.
    실제 PEG 는 EPS 증가율을 쓰지만 KIS 가 EPS 증가율을 직접 주지 않아
    영업이익증가율로 근사합니다.
  - [추가] 수익성비율 (매출액순이익률·매출총이익률) -- get_profit_ratio() 연동.
    ROE 가 같아도 마진이 개선되는 회사인지 구분하는 데 씀.
  - [추가] 유동비율 (유동자산÷유동부채) -- get_balance_sheet() 연동.
    "당장 단기 자금 위기는 없는지" 보는 지표.
  - [추가] 애널리스트 목표주가 괴리율 -- get_invest_opinion() 연동.
    증권사들이 보는 추가 상승여력. 커버리지가 없는 종목도 많아 하드필터에는
    안 쓰고 참고 점수로만 반영.
  - [점수 재구성] 종합점수 = 저평가(0.35) + 우량(0.35) + 성장(0.20) + 애널리스트(0.10)
    저평가 점수에 PEG, 우량 점수에 마진·유동비율을 포함하도록 확장.

[ 판단 기준 (config.py 의 SCREENER 클래스에서 숫자 조정 가능) ]
  저평가 여부 -- PER, PBR, PEG 이 낮을수록 이익/자산/성장 대비 주가가 싸다고 봄
  우량 여부   -- ROE·마진이 높고, 부채비율은 낮고 유동비율은 높고, 당기순이익이
               흑자면 재무가 튼튼하다고 봄
  성장 여부   -- 매출액 증가율이 플러스면 회사가 커지고 있다고 봄
  전문가 의견 -- 증권사 목표주가가 현재가보다 높으면 추가 참고점수

  단, 아래 "하드 필터"를 하나라도 통과하지 못하면 점수와 무관하게 후보에서 제외합니다.
  (예: 적자 회사는 아무리 PBR 이 낮아도 추천하지 않음)

[ 데이터가 없을 때 ]
KIS API 가 특정 종목의 특정 지표를 못 주는 경우가 있습니다 (0 으로 옴).
이런 경우 "모른다"로 보고 하드필터는 관대하게(통과), 점수는 중립(50점)으로 처리합니다.
즉 데이터 부족이 종목을 억울하게 탈락시키지 않도록 했습니다 -- 다만 그만큼
점수의 신뢰도는 낮아지니, 결과를 볼 때 reasons 항목을 꼭 같이 확인하세요.
"""
import logging
import time

from config import SCREENER, WEIGHT_PROFILES, DEFAULT_WEIGHT_PROFILE
from universe import name_of

logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _value_score(per: float, pbr: float, peg: float) -> float:
    """PER/PBR/PEG 이 기준치보다 얼마나 낮은지 -> 0~100점 (낮을수록 고득점)."""
    per_score = _clamp((SCREENER.PER_MAX - per) / SCREENER.PER_MAX * 100) if per > 0 else 50.0
    pbr_score = _clamp((SCREENER.PBR_MAX - pbr) / SCREENER.PBR_MAX * 100) if pbr > 0 else 50.0
    # PEG 1.0 이하 = 저평가, 2.0 이상 = 고평가로 봄 (전통적인 피터 린치 기준)
    peg_score = _clamp((2.0 - peg) / 2.0 * 100) if peg > 0 else 50.0
    return (per_score + pbr_score + peg_score) / 3


def _quality_score(roe: float, debt_ratio: float, net_margin: float, current_ratio: float) -> float:
    """ROE·마진·유동비율은 높을수록, 부채비율은 낮을수록 고득점 -> 0~100점."""
    roe_score    = _clamp(roe / 30.0 * 100)          # ROE 30% = 만점
    debt_score   = _clamp((SCREENER.DEBT_RATIO_MAX - debt_ratio)
                           / SCREENER.DEBT_RATIO_MAX * 100) if debt_ratio > 0 else 50.0
    margin_score = _clamp(net_margin / 20.0 * 100) if net_margin != 0 else 50.0   # 순이익률 20% = 만점
    # 유동비율 50%(위험)~200%(우량) 를 0~100점으로. 데이터 없으면 중립.
    current_score = _clamp((current_ratio - 50.0) / 150.0 * 100) if current_ratio > 0 else 50.0
    return (roe_score + debt_score + margin_score + current_score) / 4


def _growth_score(revenue_growth: float) -> float:
    """매출액 증가율 -20%~+20% 를 0~100점으로 환산 (그 밖은 양끝으로 고정)."""
    return _clamp((revenue_growth + 20.0) / 40.0 * 100)


def _analyst_score(upside: float, has_opinion: bool) -> float:
    """
    애널리스트 목표주가 괴리율 -> 0~100점.
    괴리율 0% = 중립(50점), +20%p 마다 +50점, 최대/최소 clamp.
    커버리지 자체가 없는 종목은 중립(50점) 처리 (안 좋게 보지 않음).
    """
    if not has_opinion:
        return 50.0
    return _clamp(50.0 + upside * 2.5)


def fetch_metrics(code: str, api, name: str = None) -> dict:
    """
    KIS API 를 호출해 한 종목의 재무 지표를 한데 모아 반환.

    Returns (하나라도 조회 실패 시 해당 값은 0 으로 채워짐)
    -------
    {
      "code", "name", "price",
      "per", "pbr", "debt_ratio",                          # get_fundamentals
      "roe", "eps", "bps", "revenue_growth", "op_growth",  # financial-ratio + growth-ratio
      "net_income",                                        # income-statement 최신 분기
      "net_margin", "gross_margin",                         # get_profit_ratio
      "current_ratio",                                      # get_balance_sheet
      "peg",                                                # PER ÷ op_growth 근사치
      "analyst_upside", "has_analyst_opinion",               # get_invest_opinion
    }
    """
    fundamentals  = api.get_fundamentals(code)
    fin_ratio     = api.get_financial_ratio(code)
    growth        = api.get_growth_ratio(code)
    income        = api.get_income_statement(code)
    profit_ratio  = api.get_profit_ratio(code)
    balance_sheet = api.get_balance_sheet(code)
    opinion       = api.get_invest_opinion(code)

    net_income = income[0]["net_income"] if income else 0.0

    # ROE 는 financial-ratio 값을 우선 사용, 없으면 profit-ratio 값으로 대체
    roe = fin_ratio.get("roe", 0.0) or profit_ratio.get("roe", 0.0) or 0.0

    # 매출액 증가율은 growth-ratio(전용 API) 우선, 없으면 financial-ratio 의 grs 로 대체
    revenue_growth = growth.get("revenue_growth", 0.0) or fin_ratio.get("grs", 0.0) or 0.0
    op_growth      = growth.get("op_growth",      0.0) or fin_ratio.get("op_growth", 0.0) or 0.0

    # 유동비율 = 유동자산 / 유동부채 x 100 (최신 분기 기준)
    current_ratio = 0.0
    if balance_sheet:
        latest = balance_sheet[0]
        if latest["current_liab"] > 0:
            current_ratio = latest["current_asset"] / latest["current_liab"] * 100

    # PEG = PER / 영업이익증가율 (EPS 증가율 데이터가 없어 영업이익증가율로 근사)
    per = fundamentals.get("per", 0.0) or 0.0
    peg = per / op_growth if per > 0 and op_growth > 0 else 0.0

    return {
        "code":                code,
        "name":                name or name_of(code),
        "price":               api.current_price(code),
        "per":                 per,
        "pbr":                 fundamentals.get("pbr", 0.0) or 0.0,
        "debt_ratio":          fundamentals.get("debt_ratio", 0.0) or 0.0,
        "roe":                 roe,
        "eps":                 fin_ratio.get("eps", 0.0) or 0.0,
        "bps":                 fin_ratio.get("bps", 0.0) or 0.0,
        "revenue_growth":      revenue_growth,
        "op_growth":           op_growth,
        "net_income":          net_income,
        "net_margin":          profit_ratio.get("net_margin", 0.0) or 0.0,
        "gross_margin":        profit_ratio.get("gross_margin", 0.0) or 0.0,
        "current_ratio":       round(current_ratio, 1),
        "peg":                 round(peg, 2),
        "analyst_upside":      opinion.get("upside", 0.0),
        "has_analyst_opinion": bool(opinion),
    }


def evaluate(metrics: dict) -> dict:
    """
    fetch_metrics() 결과를 받아 필터 통과 여부 + 점수 + 이유를 계산.
    KIS API 호출 없이 순수 계산만 하므로 테스트하기 쉽습니다.
    """
    per, pbr, peg      = metrics["per"], metrics["pbr"], metrics["peg"]
    roe                = metrics["roe"]
    debt_ratio         = metrics["debt_ratio"]
    net_margin         = metrics["net_margin"]
    current_ratio      = metrics["current_ratio"]
    revenue_growth     = metrics["revenue_growth"]
    net_income         = metrics["net_income"]
    price              = metrics["price"]
    upside             = metrics["analyst_upside"]
    has_opinion        = metrics["has_analyst_opinion"]

    reasons = []
    passes  = True

    # 현재가 조회 자체가 실패한 종목(API 오류 등)은 다른 지표도 신뢰할 수 없으므로
    # 점수를 매기지 않고 바로 제외. (PER/PBR 이 0 인 게 "저평가"로 오인되는 것 방지)
    if price <= 0:
        return {
            **metrics,
            "passes_filter": False,
            "value_score": 0.0, "quality_score": 0.0, "growth_score": 0.0,
            "analyst_score": 0.0, "scores": {p: 0.0 for p in WEIGHT_PROFILES}, "score": 0.0,
            "reasons": ["현재가 조회 실패 -- 데이터 없음 (KIS API 응답 오류로 추정)"],
        }

    # ── 하드 필터 (하나라도 실패하면 후보 제외) ──────────────────────────────
    # PEG·마진·유동비율·애널리스트 의견은 데이터 신뢰도가 낮거나 커버리지가
    # 없는 경우가 많아 하드 필터에는 넣지 않고 점수에만 반영합니다.
    if 0 < per < SCREENER.PER_MIN:
        passes = False
        reasons.append(f"PER {per:.2f}배로 기준({SCREENER.PER_MIN}배) 미만 -- 데이터 이상치 가능성")
    elif per > SCREENER.PER_MAX:
        passes = False
        reasons.append(f"PER {per:.1f}배로 기준({SCREENER.PER_MAX}배) 초과 -> 고평가")
    if pbr > 0 and pbr > SCREENER.PBR_MAX:
        passes = False
        reasons.append(f"PBR {pbr:.2f}배로 기준({SCREENER.PBR_MAX}배) 초과 -> 고평가")
    if roe < SCREENER.ROE_MIN:
        passes = False
        reasons.append(f"ROE {roe:.1f}%로 기준({SCREENER.ROE_MIN}%) 미달 -> 수익성 부족")
    if debt_ratio > 0 and debt_ratio > SCREENER.DEBT_RATIO_MAX:
        passes = False
        reasons.append(f"부채비율 {debt_ratio:.0f}%로 기준({SCREENER.DEBT_RATIO_MAX}%) 초과 -> 재무 위험")
    if revenue_growth < SCREENER.MIN_REVENUE_GROWTH:
        passes = False
        reasons.append(f"매출액 증가율 {revenue_growth:.1f}%로 역성장")
    if SCREENER.REQUIRE_POSITIVE_NET_INCOME and net_income <= 0:
        passes = False
        reasons.append("최근 분기 당기순이익 적자")

    # ── 점수 계산 (필터 통과 여부와 무관하게 항상 계산 -- 참고용) ─────────────
    # 4개 구성점수는 스타일과 무관한 "원재료"이고, 이걸 어떤 비중으로 합칠지는
    # config.WEIGHT_PROFILES 의 프로필(딥밸류/밸런스/GARP)마다 다르게 계산합니다.
    # 그래서 API 재호출 없이 여러 투자 스타일 순위를 동시에 볼 수 있습니다.
    value_score   = _value_score(per, pbr, peg)
    quality_score = _quality_score(roe, debt_ratio, net_margin, current_ratio)
    growth_score  = _growth_score(revenue_growth)
    analyst_score = _analyst_score(upside, has_opinion)

    scores = {}
    for profile, w in WEIGHT_PROFILES.items():
        scores[profile] = round(
            value_score * w["value"] + quality_score * w["quality"]
            + growth_score * w["growth"] + analyst_score * w["analyst"], 1
        )

    if passes:
        peg_txt      = f"{peg:.2f}" if peg > 0 else "N/A"
        upside_txt   = f"{upside:+.1f}%" if has_opinion else "커버리지 없음"
        reasons.insert(0, (
            f"PER {per:.1f}배 / PBR {pbr:.2f}배 / PEG {peg_txt} (저평가), "
            f"ROE {roe:.1f}% / 순이익률 {net_margin:.1f}% / 부채비율 {debt_ratio:.0f}% / "
            f"유동비율 {current_ratio:.0f}% (우량), "
            f"매출증가율 {revenue_growth:.1f}% (성장), "
            f"애널리스트 목표가 괴리율 {upside_txt}"
        ))

    return {
        **metrics,
        "passes_filter": passes,
        "value_score":   round(value_score, 1),
        "quality_score": round(quality_score, 1),
        "growth_score":  round(growth_score, 1),
        "analyst_score": round(analyst_score, 1),
        "scores":        scores,                          # {"deep_value":.., "balanced":.., "garp":..}
        "score":         scores[DEFAULT_WEIGHT_PROFILE],   # 하위호환 + 기본 정렬 기준
        "reasons":       reasons,
    }


def scan_universe(codes: list, api, on_progress=None, names: dict = None) -> list:
    """
    종목 코드 리스트를 전부 조회 + 평가.
    "저평가 우량주" 필터를 통과했는지와 무관하게 스캔한 전체 결과를 그대로 반환합니다
    -- select_value_picks() / select_growth_picks() 가 여기서 각자 원하는 기준으로
    골라내므로, API 호출은 한 번만 하고 두 가지 관점(저평가·성장)으로 재사용할 수 있습니다.

    Parameters
    ----------
    codes       : 스캔할 종목 코드 리스트 (universe.get_universe() 결과 등)
    api         : kis_api.KIS 인스턴스
    on_progress : (index, total, label) 를 매 종목마다 호출하는 콜백 (진행상황 표시용)
    names       : {code: name} -- KIS 랭킹 API 등에서 이미 받아온 종목명이 있으면 넘겨서
                  universe.py 의 고정 사전에 없는 종목도 코드 대신 실제 이름으로 표시
    """
    names = names or {}
    results = []
    total = len(codes)
    for i, code in enumerate(codes, start=1):
        name = names.get(code)
        if on_progress:
            on_progress(i, total, f"{name or code}({code})" if name else code)
        try:
            metrics = fetch_metrics(code, api, name=name)
            results.append(evaluate(metrics))
        except Exception as e:
            logger.warning(f"[value_screener] {code} 평가 실패: {e}")
        time.sleep(0.15)   # KIS API 초당 호출 제한 대비

    return results


def select_value_picks(results: list, top_n: int = None, profile: str = DEFAULT_WEIGHT_PROFILE) -> list:
    """
    scan_universe() 결과 중 "저평가 우량주" 하드필터를 통과한 종목만,
    지정한 가중치 프로필(config.WEIGHT_PROFILES) 점수 기준으로 정렬해 반환.

    같은 하드필터 통과 집합을 profile 만 바꿔서 여러 번 호출하면
    "딥밸류로 보면 1등, GARP로 보면 3등" 처럼 스타일별 순위를 비교할 수 있습니다.
    """
    # r["score"] 는 여기서 덮어쓰지 않습니다 -- 같은 result 객체가 여러 프로필
    # 순위표에 동시에 쓰이므로, 특정 프로필로 정렬한다고 다른 표의 점수 표시가
    # 바뀌면 안 됩니다. 표시는 항상 scores[profile] 을 직접 참조하세요.
    passed = [r for r in results if r["passes_filter"]]
    passed.sort(key=lambda r: r["scores"][profile], reverse=True)
    return passed[:top_n] if top_n else passed


def select_growth_picks(results: list, top_n: int = None) -> list:
    """
    scan_universe() 결과 중 "전분기 대비 성장률이 좋은 종목"만 매출액 증가율순으로.

    저평가 우량주 필터(PER/PBR/부채비율 등)와는 별개 기준입니다 -- 값이 비싸도
    (PER/PBR 이 높아도) 성장률만 기준을 넘으면 여기에는 포함됩니다.
    기준값은 config.SCREENER.GROWTH_MIN (기본 15%) 이며, 현재가 조회 자체가
    실패한 종목(데이터 없음)은 제외합니다.
    """
    candidates = [
        r for r in results
        if r["price"] > 0 and r["revenue_growth"] >= SCREENER.GROWTH_MIN
    ]
    candidates.sort(key=lambda r: (r["revenue_growth"], r["op_growth"]), reverse=True)

    picks = candidates[:top_n] if top_n else candidates
    for r in picks:
        r["growth_reason"] = (
            f"매출액 증가율 {r['revenue_growth']:.1f}% / "
            f"영업이익 증가율 {r['op_growth']:.1f}% (전분기 대비 성장 우수)"
        )
    return picks
