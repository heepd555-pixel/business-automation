"""
view_report.py -- 저장된 JSON 리포트를 표로 다시 보여주는 도구 (신규 파일)

[ 이 파일이 왜 필요한가 ]
python main.py 를 실행하면 화면에 표가 쭉 지나가고, 그 결과가 reports/*.json 으로
저장됩니다. 터미널을 닫았거나 스크롤해서 놓쳤을 때, 또는 예전 리포트를 다시 보고
싶을 때 JSON 파일을 열어보면 사람이 읽기 불편합니다. 이 파일은 main.py 가 화면에
찍던 것과 똑같은 표 포맷으로 JSON 리포트를 다시 그려줍니다. (API 호출 없음 -- 이미
저장된 파일만 읽어서 즉시 출력)

[ 사용 방법 ]
    python view_report.py                                       # 가장 최근 리포트
    python view_report.py --file reports/screening_20260707_125957.json
    python view_report.py --list                                # 저장된 리포트 목록만 보기
"""
import argparse
import glob
import json
import os

from main import _print_table, _print_growth_table, PROFILE_LABELS

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")


def _list_reports() -> list:
    return sorted(glob.glob(os.path.join(REPORT_DIR, "screening_*.json")))


def _latest_report() -> str:
    files = _list_reports()
    if not files:
        raise FileNotFoundError(
            f"{REPORT_DIR} 에 리포트 파일이 없습니다. 먼저 'python main.py' 를 실행해 리포트를 만드세요."
        )
    return files[-1]


def _print_criteria(criteria: dict):
    if not criteria:
        return
    simple = {k: v for k, v in criteria.items() if not isinstance(v, dict)}
    print("사용된 기준값: " + ", ".join(f"{k}={v}" for k, v in simple.items()))


def show_report(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    print(f"리포트 파일: {path}")
    print(f"생성 시각: {data.get('generated_at', '알 수 없음')}")
    _print_criteria(data.get("criteria", {}))

    kr_by_profile = data.get("kr_value_results_by_profile", {})
    for profile, label in PROFILE_LABELS.items():
        if profile in kr_by_profile:
            _print_table(f"국내 주식 -- 저평가 우량주 [{label}]",
                         kr_by_profile[profile], columns_extra=True, profile=profile)

    growth = data.get("kr_growth_results", [])
    if growth:
        _print_growth_table(growth)

    us = data.get("us_results", [])
    if us:
        _print_table("미국 주식 (부채비율·성장률 데이터 없음 -- PER/PBR/근사ROE 만 반영)",
                     us, columns_extra=False)

    if not kr_by_profile and not growth and not us:
        print("\n이 리포트에는 표시할 결과가 없습니다 (예전 포맷이거나 빈 스캔 결과일 수 있음).")


def main():
    parser = argparse.ArgumentParser(description="저장된 스크리닝 리포트(JSON)를 표로 다시 보여주기")
    parser.add_argument("--file", type=str, default=None,
                         help="볼 리포트 파일 경로 (기본: reports/ 안의 가장 최근 파일)")
    parser.add_argument("--list", action="store_true", help="저장된 리포트 파일 목록만 출력")
    args = parser.parse_args()

    if args.list:
        files = _list_reports()
        if not files:
            print(f"{REPORT_DIR} 에 리포트 파일이 없습니다.")
            return
        print(f"저장된 리포트 {len(files)}개 (오래된 순):")
        for f in files:
            print(" ", os.path.basename(f))
        return

    path = args.file or _latest_report()
    show_report(path)


if __name__ == "__main__":
    main()
