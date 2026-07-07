"""
value_screener.py -- 저평가 우량주 스크리너 (신규 파일)

[ 이 파일이 하는 일 ]
예전 financial_filter.py 는 "재무가 나쁜 종목을 매매 후보에서 제외"하는
용도였습니다 (매매 프로그램의 부품 중 하나). 이 파일은 그 역할을 완전히
새로 만든 것으로, 목적 자체가 다릅니다:

    "지금 가진 종목 목록 중에서, 재무제표(대차대조표·손익계산서)를 기준으로
     '좋은 회사인데 주가는 싼' 종목을 찾아서 점수를 매기고 순위를 매긴다."

[ 판단 기준 (config.py 의 SCREENER 클래스에서 숫자 조정 가능) ]
  저평가 여부 -- PER, PBR 이 낮을수록 이익/자산 대비 주가가 싸다고 봄
  우량 여부   -- ROE 가 높고, 부채비율이 낮고, 당기순이익이 흑자면 재무가 튼튼하다고 봄
  성장 여부   -- 매출액 증가율이 플러스면 회사가 커지고 있다고 봄

  이 세 가지를 각각 0~100점으로 환산한 뒤,
      종합점수 = 저평가점수 x 0.4 + 우량점수 x 0.4 + 성장점수 x 0.2
  로 합산합니다. 종합점수가 높을수록 "좋은데 싼 회사"에 가깝습니다.

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

from config import SCREENER
from universe import name_of

logger = logging.getLogger(__name__)


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _value_score(per: float, pbr: float) -> float:
    """PER/PBR 이 기준치보다 얼마나 낮은지 -> 0~100점 (낮을수록 고득점)."""
    per_score = _clamp((SCREENER.PER_MAX - per) / SCREENER.PER_MAX * 100) if per > 0 else 50.0
    pbr_score = _clamp((SCREENER.PBR_MAX - pbr) / SCREENER.PBR_MAX * 100) if pbr > 0 else 50.0
    return (per_score + pbr_score) / 2


def _quality_score(roe: float, debt_ratio: float) -> float:
    """ROE 는 높을수록, 부채비율은 낮을수록 고득점 -> 0~100점."""
    roe_score  = _clamp(roe / 30.0 * 100)                                        # ROE 30% = 만점
    debt_score = _clamp((SCREENER.DEBT_RATIO_MAX - debt_ratio)
                         / SCREENER.DEBT_RATIO_MAX * 100) if debt_ratio > 0 else 50.0
    return (roe_score + debt_score) / 2


def _growth_score(revenue_growth: float) -> float:
    """매출액 증가율 -20%~+20% 를 0~100점으로 환산 (그 밖은 양끝으로 고정)."""
    return _clamp((revenue_growth + 20.0) / 40.0 * 100)


def fetch_metrics(code: str, api, name: str = None) -> dict:
    """
    KIS API 를 호출해 한 종목의 재무 지표를 한데 모아 반환.

    Returns (하나라도 조회 실패 시 해당 값은 0 으로 채워짐)
    -------
    {
      "code", "name", "price",
      "per", "pbr", "debt_ratio",                 # get_fundamentals
      "roe", "eps", "bps", "revenue_growth", "op_growth",  # financial-ratio + growth-ratio
      "net_income",                                # income-statement 최신 분기
    }
    """
    fundamentals = api.get_fundamentals(code)
    fin_ratio    = api.get_financial_ratio(code)
    growth       = api.get_growth_ratio(code)
    income       = api.get_income_statement(code)

    net_income = income[0]["net_income"] if income else 0.0

    # ROE 는 financial-ratio 값을 우선 사용, 없으면 0
    roe = fin_ratio.get("roe", 0.0) or 0.0

    # 매출액 증가율은 growth-ratio(전용 API) 우선, 없으면 financial-ratio 의 grs 로 대체
    revenue_growth = growth.get("revenue_growth", 0.0) or fin_ratio.get("grs", 0.0) or 0.0
    op_growth      = growth.get("op_growth",      0.0) or fin_ratio.get("op_growth", 0.0) or 0.0

    return {
        "code":           code,
        "name":           name or name_of(code),
        "price":          api.current_price(code),
        "per":            fundamentals.get("per", 0.0) or 0.0,
        "pbr":            fundamentals.get("pbr", 0.0) or 0.0,
        "debt_ratio":     fundamentals.get("debt_ratio", 0.0) or 0.0,
        "roe":            roe,
        "eps":            fin_ratio.get("eps", 0.0) or 0.0,
        "bps":            fin_ratio.get("bps", 0.0) or 0.0,
        "revenue_growth": revenue_growth,
        "op_growth":      op_growth,
        "net_income":     net_income,
    }


def evaluate(metrics: dict) -> dict:
    """
    fetch_metrics() 결과를 받아 필터 통과 여부 + 점수 + 이유를 계산.
    KIS API 호출 없이 순수 계산만 하므로 테스트하기 쉽습니다.
    """
    per, pbr           = metrics["per"], metrics["pbr"]
    roe                = metrics["roe"]
    debt_ratio         = metrics["debt_ratio"]
    revenue_growth     = metrics["revenue_growth"]
    net_income         = metrics["net_income"]
    price              = metrics["price"]

    reasons = []
    passes  = True

    # 현재가 조회 자체가 실패한 종목(API 오류 등)은 다른 지표도 신뢰할 수 없으므로
    # 점수를 매기지 않고 바로 제외. (PER/PBR 이 0 인 게 "저평가"로 오인되는 것 방지)
    if price <= 0:
        return {
            **metrics,
            "passes_filter": False,
            "value_score": 0.0, "quality_score": 0.0, "growth_score": 0.0, "score": 0.0,
            "reasons": ["현재가 조회 실패 -- 데이터 없음 (KIS API 응답 오류로 추정)"],
        }

    # ── 하드 필터 (하나라도 실패하면 후보 제외) ──────────────────────────────
    if per > 0 and per > SCREENER.PER_MAX:
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
    value_score   = _value_score(per, pbr)
    quality_score = _quality_score(roe, debt_ratio)
    growth_score  = _growth_score(revenue_growth)
    total_score   = round(value_score * 0.4 + quality_score * 0.4 + growth_score * 0.2, 1)

    if passes:
        reasons.insert(0, (
            f"PER {per:.1f}배 / PBR {pbr:.2f}배 (저평가), "
            f"ROE {roe:.1f}% / 부채비율 {debt_ratio:.0f}% (우량), "
            f"매출증가율 {revenue_growth:.1f}% (성장)"
        ))

    return {
        **metrics,
        "passes_filter": passes,
        "value_score":   round(value_score, 1),
        "quality_score": round(quality_score, 1),
        "growth_score":  round(growth_score, 1),
        "score":         total_score,
        "reasons":       reasons,
    }


def rank_universe(codes: list, api, top_n: int = None, on_progress=None, names: dict = None) -> list:
    """
    종목 코드 리스트를 전부 조회 + 평가해서, 필터를 통과한 종목만
    점수 내림차순으로 정렬해 반환.

    Parameters
    ----------
    codes       : 스캔할 종목 코드 리스트 (universe.get_universe() 결과 등)
    api         : kis_api.KIS 인스턴스
    top_n       : 상위 몇 개만 반환할지 (None 이면 전체)
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

    passed = [r for r in results if r["passes_filter"]]
    passed.sort(key=lambda r: r["score"], reverse=True)

    if top_n:
        return passed[:top_n]
    return passed
