"""
main.py v10 -- 저평가 우량주 + 성장주 스크리너 실행 (참고용, 매매 없음)

[ v10 변경사항 -- 성장주 TOP N 별도 추가 ]
  - "저평가 우량주" 필터(PER/PBR/부채비율 등)와 "성장주"(전분기 대비 매출·영업이익
    증가율이 좋은 종목)는 서로 다른 관점이라 하나로 섞지 않고 표를 분리했습니다.
    같은 스캔 데이터를 재사용하므로 API 를 두 번 호출하지 않습니다.
  - 국내(kr) 스캔에서만 제공 -- 미국(us) 은 KIS 가 성장률 데이터를 주지 않음.

[ v9 변경사항 -- 전체 종목 스캔 + 미국장 지원 ]
  - [기본값 변경] 기본 실행이 이제 config.py 의 고정 66종목이 아니라,
    KIS 랭킹 API로 실시간 조회한 "국내 시가총액 상위 유니버스"(보통 300~500종목)를 스캔.
    (진짜 코스피/코스닥 전체 2500여개는 아님 -- full_universe.py 상단 설명 참고)
  - [추가] --market {kr,us,all} -- 국내(kr) / 미국(us) / 둘 다(all) 선택
  - [추가] --quick -- 예전처럼 config.py 의 고정 66종목만 빠르게 스캔 (테스트용)
  - [기존유지] --top N, --all(필터 통과 전부 출력) -- 단, --all 은 이제
    "필터 통과 종목 전부"라는 뜻과 "kr+us 둘 다"라는 뜻이 겹치므로
    시장 선택은 --market, 개수 선택은 --top/--show-all 로 분리함

[ 사용 방법 ]
    python main.py                     # 국내 시가총액 상위 유니버스 스캔 (저평가+성장 각 상위 20개)
    python main.py --market us         # 미국(나스닥/뉴욕/아멕스 상위 100개씩) 스캔
    python main.py --market all        # 국내 + 미국 모두 스캔
    python main.py --quick             # 예전 고정 66종목만 빠르게 스캔 (테스트용)
    python main.py --top 10            # 상위 10개만 출력
    python main.py --show-all          # 필터 통과 종목 전부 출력

[ 초보자 설명 ]
이 프로그램은 아무것도 사거나 팔지 않습니다.
"이 종목들 중에 재무제표 기준으로 괜찮은데 싸 보이는 회사", 그리고
"전분기보다 매출·이익이 많이 늘어난 회사"를 훑어보고 점수를 매겨서
보여주기만 하는 참고용 도구입니다.
전체 종목 스캔은 종목 수가 많아 수 분 정도 걸릴 수 있습니다.
투자 판단과 실제 매매는 반드시 본인이 직접 하세요.
"""
import argparse
import json
import logging
import os
from datetime import datetime

from config import validate_api_keys, SCREENER, SYMBOLS, WEIGHT_PROFILES
from kis_api import KIS
from universe import format_symbol
from value_screener import scan_universe, select_value_picks, select_growth_picks
from value_screener_us import rank_us_universe
import full_universe

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _print_universe_progress(i: int, total: int, label: str):
    print(f"\r  유니버스 수집 중... {i}/{total}  ({label})" + " " * 15, end="", flush=True)


def _print_scan_progress(i: int, total: int, label: str):
    print(f"\r  스캔 중... {i}/{total}  ({label})" + " " * 15, end="", flush=True)


def _print_table(title: str, results: list, columns_extra: bool, profile: str = None):
    print(f"\n\n=== {title} ===")
    if not results:
        print("조건을 통과한 종목이 없습니다. config.py 의 SCREENER 기준값을 완화해보세요.")
        return

    if columns_extra:
        header = (f"{'순위':>4} {'종목':<18} {'현재가':>12} {'PER':>6} {'PBR':>6} {'PEG':>5} "
                   f"{'ROE%':>7} {'부채%':>7} {'유동%':>7} {'매출성장%':>9} {'목표가괴리%':>10} {'점수':>6}")
    else:
        header = f"{'순위':>4} {'종목':<18} {'현재가':>12} {'PER':>6} {'PBR':>6} {'ROE%(근사)':>10} {'점수':>6}"
    print(header)
    print("-" * len(header))
    for rank, r in enumerate(results, start=1):
        label = f"{r['name']}({r['code']})"
        # KR 은 프로필별 점수(scores[profile])를, US 는 단일 score 를 그대로 표시.
        score = r["scores"][profile] if (columns_extra and profile) else r["score"]
        if columns_extra:
            upside_str = f"{r['analyst_upside']:+.1f}" if r["has_analyst_opinion"] else "N/A"
            print(
                f"{rank:>4} {label:<18} {r['price']:>12,.2f} "
                f"{r['per']:>6.1f} {r['pbr']:>6.2f} {r['peg']:>5.2f} "
                f"{r['roe']:>7.1f} {r['debt_ratio']:>7.0f} {r['current_ratio']:>7.0f} "
                f"{r['revenue_growth']:>9.1f} {upside_str:>10} {score:>6.1f}"
            )
        else:
            print(
                f"{rank:>4} {label:<18} {r['price']:>12,.2f} "
                f"{r['per']:>6.1f} {r['pbr']:>6.2f} {r['roe']:>10.1f} {score:>6.1f}"
            )

    print("\n[상세 이유]")
    for rank, r in enumerate(results, start=1):
        print(f" {rank}. {r['name']}({r['code']}) -- {r['reasons'][0]}")


def _print_growth_table(results: list):
    print(f"\n\n=== 국내 주식 -- 성장주 TOP (전분기 대비 매출·영업이익 증가율 기준, 저평가 필터와 무관) ===")
    if not results:
        print(f"매출액 증가율 {SCREENER.GROWTH_MIN}% 이상인 종목이 없습니다. config.py 의 GROWTH_MIN 을 낮춰보세요.")
        return

    header = f"{'순위':>4} {'종목':<18} {'현재가':>12} {'PER':>6} {'PBR':>6} {'매출성장%':>9} {'영업익성장%':>10}"
    print(header)
    print("-" * len(header))
    for rank, r in enumerate(results, start=1):
        label = f"{r['name']}({r['code']})"
        print(
            f"{rank:>4} {label:<18} {r['price']:>12,.2f} "
            f"{r['per']:>6.1f} {r['pbr']:>6.2f} {r['revenue_growth']:>9.1f} {r['op_growth']:>10.1f}"
        )

    print("\n[상세 이유]")
    for rank, r in enumerate(results, start=1):
        print(f" {rank}. {r['name']}({r['code']}) -- {r['growth_reason']}")


def _save_report(kr_value_by_profile: dict, kr_growth_results: list, us_results: list) -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORT_DIR, f"screening_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "criteria": {
                "PER_MAX":            SCREENER.PER_MAX,
                "PBR_MAX":            SCREENER.PBR_MAX,
                "ROE_MIN":            SCREENER.ROE_MIN,
                "DEBT_RATIO_MAX":     SCREENER.DEBT_RATIO_MAX,
                "MIN_REVENUE_GROWTH": SCREENER.MIN_REVENUE_GROWTH,
                "GROWTH_MIN":         SCREENER.GROWTH_MIN,
                "WEIGHT_PROFILES":    WEIGHT_PROFILES,
            },
            "kr_value_results_by_profile": kr_value_by_profile,
            "kr_growth_results":           kr_growth_results,
            "us_results":                  us_results,
        }, f, ensure_ascii=False, indent=2)
    return path


PROFILE_LABELS = {
    "deep_value": "딥밸류 (저평가 최우선)",
    "balanced":   "밸런스 (저평가+우량 동률)",
    "garp":       "GARP (적정가 성장주)",
}


def _run_kr(quick: bool, top_n):
    """
    국내 유니버스를 한 번만 스캔하고, 하드필터 통과 종목을 딥밸류/밸런스/GARP
    세 가지 가중치 프로필로 각각 재정렬 + 성장주(전분기 대비) 관점까지 반환.
    스캔(API 호출)은 한 번만 하고, 이후는 이미 계산해둔 점수를 재사용합니다.
    """
    api = KIS()
    if quick:
        codes = SYMBOLS
        names = {}   # --quick 은 universe.name_of() 의 고정 사전을 그대로 사용
        print(f"\n[국내] 고정 유니버스(--quick) 스캔 시작 -- 총 {len(codes)}종목")
    else:
        print("\n[국내] 시가총액 상위 유니버스 수집 중 (KOSPI+KOSDAQ, 가격대별 분할 조회)...")
        rows  = full_universe.fetch_kr_universe(api, on_progress=_print_universe_progress)
        codes = [r["code"] for r in rows]
        names = {r["code"]: r["name"] for r in rows}   # KIS 가 준 실제 종목명 활용
        print(f"\n[국내] 유니버스 수집 완료 -- 총 {len(codes)}종목 스캔 시작")

    all_results = scan_universe(codes, api, on_progress=_print_scan_progress, names=names)

    value_picks_by_profile = {
        profile: select_value_picks(all_results, top_n=top_n, profile=profile)
        for profile in PROFILE_LABELS
    }
    growth_picks = select_growth_picks(all_results, top_n=top_n)
    return value_picks_by_profile, growth_picks


def _run_us(top_n) -> list:
    api = KIS()
    print("\n[미국] 시가총액 상위 유니버스 수집 중 (나스닥/뉴욕/아멕스 각 상위 100개)...")
    rows = full_universe.fetch_us_universe(api, on_progress=_print_universe_progress)
    print(f"\n[미국] 유니버스 수집 완료 -- 총 {len(rows)}종목 스캔 시작")
    return rank_us_universe(rows, api, top_n=top_n, on_progress=_print_scan_progress)


def main():
    parser = argparse.ArgumentParser(description="재무제표 기반 저평가 우량주 스크리너 (참고용)")
    parser.add_argument("--market", choices=["kr", "us", "all"], default="kr",
                         help="스캔할 시장 (기본: kr)")
    parser.add_argument("--quick", action="store_true",
                         help="국내 스캔 시 config.py 의 고정 66종목만 빠르게 조회 (전체 유니버스 수집 생략)")
    parser.add_argument("--top", type=int, default=SCREENER.TOP_N,
                         help="상위 N개만 출력 (기본: config.SCREENER.TOP_N)")
    parser.add_argument("--show-all", action="store_true",
                         help="필터를 통과한 종목 전부 출력 (--top 무시)")
    args = parser.parse_args()

    validate_api_keys()

    top_n = None if args.show_all else args.top

    kr_value_by_profile, kr_growth_results, us_results = {}, [], []
    if args.market in ("kr", "all"):
        kr_value_by_profile, kr_growth_results = _run_kr(quick=args.quick, top_n=top_n)
        for profile, label in PROFILE_LABELS.items():
            _print_table(f"국내 주식 -- 저평가 우량주 [{label}]",
                         kr_value_by_profile[profile], columns_extra=True, profile=profile)
        _print_growth_table(kr_growth_results)

    if args.market in ("us", "all"):
        us_results = _run_us(top_n=top_n)
        _print_table("미국 주식 (부채비율·성장률 데이터 없음 -- PER/PBR/근사ROE 만 반영)", us_results, columns_extra=False)

    path = _save_report(kr_value_by_profile, kr_growth_results, us_results)
    print(f"\n리포트 저장 완료: {path}")
    print("\n※ 이 결과는 투자 참고 자료일 뿐 투자 권유가 아닙니다. 최종 판단과 책임은 본인에게 있습니다.")


if __name__ == "__main__":
    main()
