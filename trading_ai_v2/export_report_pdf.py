"""
export_report_pdf.py -- 저장된 JSON 리포트를 PDF 파일로 내보내기 (신규 파일)

[ 왜 필요한가 ]
콘솔(cmd)에서 표를 보는 게 불편하다는 피드백으로 추가했습니다. view_report.py 가
읽는 것과 똑같은 reports/*.json 리포트를, 더블클릭으로 바로 열어볼 수 있는 PDF
파일로 저장합니다. (API 호출 없음 -- 이미 저장된 파일만 읽어서 변환하므로 즉시 완료)

[ 사용법 ]
    python export_report_pdf.py                        # 가장 최근 리포트 -> PDF
    python export_report_pdf.py --file reports/screening_20260707_125957.json
    python export_report_pdf.py --out reports/my_report.pdf   # 저장 경로 지정

[ 필요 패키지 ]
    pip install fpdf2
[ 필요 폰트 ]
    한글 표시를 위해 Windows 기본 맑은 고딕(malgun.ttf/malgunbd.ttf) 을 사용합니다.
    Windows 가 아니거나 폰트 위치가 다르면 아래 KOREAN_FONT_REGULAR/BOLD 경로를 수정하세요.
"""
import argparse
import glob
import json
import logging
import os

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from main import PROFILE_LABELS

# fpdf2 가 폰트를 내장(subset)할 때 fontTools 가 디버그성 로그를 잔뜩 찍어서 조용히 시킴
logging.getLogger("fontTools").setLevel(logging.WARNING)

REPORT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

KOREAN_FONT_REGULAR = r"C:\Windows\Fonts\malgun.ttf"
KOREAN_FONT_BOLD     = r"C:\Windows\Fonts\malgunbd.ttf"

_NEXT_LINE = dict(new_x=XPos.LMARGIN, new_y=YPos.NEXT)   # cell() 뒤 "다음 줄 왼쪽 끝으로" 이동


def _latest_report() -> str:
    files = sorted(glob.glob(os.path.join(REPORT_DIR, "screening_*.json")))
    if not files:
        raise FileNotFoundError(
            f"{REPORT_DIR} 에 리포트 파일이 없습니다. 먼저 'python main.py' 를 실행해 리포트를 만드세요."
        )
    return files[-1]


class ReportPDF(FPDF):
    """맑은 고딕을 내장한 가로(landscape) A4 PDF. 표 + 종목별 상세 이유를 순서대로 그림."""

    def __init__(self):
        super().__init__(orientation="L", format="A4", unit="mm")
        self.set_auto_page_break(auto=True, margin=14)
        self.set_margins(10, 12, 10)
        if not os.path.exists(KOREAN_FONT_REGULAR):
            raise FileNotFoundError(
                f"한글 폰트를 찾을 수 없습니다: {KOREAN_FONT_REGULAR}\n"
                "Windows 가 아니라면 이 파일 상단의 KOREAN_FONT_REGULAR/BOLD 경로를 직접 지정하세요."
            )
        self.add_font("Malgun", "", KOREAN_FONT_REGULAR)
        self.add_font("Malgun", "B", KOREAN_FONT_BOLD)
        self.set_font("Malgun", size=9)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Malgun", size=8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 6, "저평가 우량주 스크리너 리포트 (참고용, 투자 권유 아님)", align="R", **_NEXT_LINE)
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def cover(self, path: str, generated_at: str, criteria: dict):
        self.add_page()
        self.set_font("Malgun", "B", 20)
        self.cell(0, 14, "저평가 우량주 스크리너 리포트", **_NEXT_LINE)
        self.set_font("Malgun", size=10)
        self.set_text_color(90, 90, 90)
        self.cell(0, 7, f"원본 파일: {os.path.basename(path)}", **_NEXT_LINE)
        self.cell(0, 7, f"생성 시각: {generated_at}", **_NEXT_LINE)
        self.ln(4)
        simple = {k: v for k, v in criteria.items() if not isinstance(v, dict)}
        if simple:
            self.set_font("Malgun", "B", 10)
            self.set_text_color(0, 0, 0)
            self.cell(0, 7, "스크리닝 기준값", **_NEXT_LINE)
            self.set_font("Malgun", size=9)
            self.set_text_color(60, 60, 60)
            for k, v in simple.items():
                self.cell(0, 6, f"  {k} = {v}", **_NEXT_LINE)
        self.ln(6)
        self.set_font("Malgun", size=9)
        self.set_text_color(150, 60, 60)
        self.set_x(self.l_margin)
        self.multi_cell(0, 5,
            "※ 이 리포트는 투자 참고 자료일 뿐 투자 권유가 아닙니다. "
            "재무제표는 과거 데이터이며, 최종 판단과 책임은 본인에게 있습니다.")
        self.set_text_color(0, 0, 0)

    def section_title(self, text):
        self.set_x(self.l_margin)
        self.set_font("Malgun", "B", 13)
        self.cell(0, 10, text, **_NEXT_LINE)
        self.set_font("Malgun", size=9)
        self.ln(1)

    def empty_note(self, text):
        self.set_x(self.l_margin)
        self.set_font("Malgun", size=9)
        self.set_text_color(120, 120, 120)
        self.multi_cell(0, 6, text)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def data_table(self, headers, widths, aligns, rows):
        row_h = 6.5

        def draw_header():
            self.set_x(self.l_margin)
            self.set_font("Malgun", "B", 8.5)
            self.set_fill_color(235, 235, 235)
            for h, w, a in zip(headers, widths, aligns):
                self.cell(w, row_h, h, border=1, align=a, fill=True)
            self.ln(row_h)

        draw_header()
        self.set_font("Malgun", size=8.5)
        for i, row in enumerate(rows):
            if self.get_y() + row_h > self.page_break_trigger:
                self.add_page()
                draw_header()
                self.set_font("Malgun", size=8.5)
            self.set_x(self.l_margin)
            fill = (i % 2 == 1)
            if fill:
                self.set_fill_color(248, 248, 248)
            for val, w, a in zip(row, widths, aligns):
                self.cell(w, row_h, str(val), border=1, align=a, fill=fill)
            self.ln(row_h)
        self.ln(3)

    def reasons_block(self, title: str, items: list):
        self.set_x(self.l_margin)
        self.set_font("Malgun", "B", 9.5)
        self.cell(0, 7, title, **_NEXT_LINE)
        self.set_font("Malgun", size=8)
        self.set_text_color(70, 70, 70)
        for i, text in enumerate(items, start=1):
            self.set_x(self.l_margin)
            self.multi_cell(0, 4.6, f"{i}. {text}")
        self.set_text_color(0, 0, 0)
        self.ln(4)


def _kr_value_section(pdf: ReportPDF, results: list, label: str):
    pdf.add_page()
    pdf.section_title(f"국내 주식 -- 저평가 우량주 [{label}]")
    if not results:
        pdf.empty_note("조건을 통과한 종목이 없습니다. config.py 의 SCREENER 기준값을 완화해보세요.")
        return

    headers = ["순위", "종목", "현재가", "PER", "PBR", "PEG", "ROE%", "부채%", "유동%", "매출성장%", "목표가괴리%", "점수"]
    widths  = [10, 48, 26, 14, 14, 12, 14, 14, 14, 20, 22, 14]
    aligns  = ["C", "L", "R", "R", "R", "R", "R", "R", "R", "R", "R", "R"]

    rows = []
    for rank, r in enumerate(results, start=1):
        upside = f"{r['analyst_upside']:+.1f}" if r.get("has_analyst_opinion") else "N/A"
        rows.append([
            rank, f"{r['name']}({r['code']})", f"{r['price']:,.0f}",
            f"{r['per']:.1f}", f"{r['pbr']:.2f}", f"{r['peg']:.2f}",
            f"{r['roe']:.1f}", f"{r['debt_ratio']:.0f}", f"{r['current_ratio']:.0f}",
            f"{r['revenue_growth']:.1f}", upside, f"{r['score']:.1f}",
        ])
    pdf.data_table(headers, widths, aligns, rows)
    pdf.reasons_block("상세 이유", [r["reasons"][0] for r in results])


def _kr_growth_section(pdf: ReportPDF, results: list):
    pdf.add_page()
    pdf.section_title("국내 주식 -- 성장주 TOP (전분기 대비 매출·영업이익 증가율 기준, 저평가 필터와 무관)")
    if not results:
        pdf.empty_note("조건을 만족하는 종목이 없습니다. config.py 의 GROWTH_MIN 을 낮춰보세요.")
        return

    headers = ["순위", "종목", "현재가", "PER", "PBR", "매출성장%", "영업익성장%"]
    widths  = [10, 55, 30, 20, 20, 25, 25]
    aligns  = ["C", "L", "R", "R", "R", "R", "R"]

    rows = []
    for rank, r in enumerate(results, start=1):
        rows.append([
            rank, f"{r['name']}({r['code']})", f"{r['price']:,.0f}",
            f"{r['per']:.1f}", f"{r['pbr']:.2f}",
            f"{r['revenue_growth']:.1f}", f"{r['op_growth']:.1f}",
        ])
    pdf.data_table(headers, widths, aligns, rows)
    pdf.reasons_block("상세 이유", [r["growth_reason"] for r in results])


def _us_section(pdf: ReportPDF, results: list):
    pdf.add_page()
    pdf.section_title("미국 주식 (부채비율·성장률 데이터 없음 -- PER/PBR/근사ROE 만 반영)")
    if not results:
        pdf.empty_note("조건을 통과한 종목이 없습니다.")
        return

    headers = ["순위", "종목", "현재가($)", "PER", "PBR", "ROE%(근사)", "점수"]
    widths  = [10, 60, 30, 20, 20, 28, 20]
    aligns  = ["C", "L", "R", "R", "R", "R", "R"]

    rows = []
    for rank, r in enumerate(results, start=1):
        rows.append([
            rank, f"{r['name']}({r['code']})", f"{r['price']:,.2f}",
            f"{r['per']:.1f}", f"{r['pbr']:.2f}", f"{r['roe']:.1f}", f"{r['score']:.1f}",
        ])
    pdf.data_table(headers, widths, aligns, rows)
    pdf.reasons_block("상세 이유", [r["reasons"][0] for r in results])


def export(path: str, out_path: str = None) -> str:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    pdf = ReportPDF()
    pdf.cover(path, data.get("generated_at", "알 수 없음"), data.get("criteria", {}))

    kr_by_profile = data.get("kr_value_results_by_profile", {})
    for profile, label in PROFILE_LABELS.items():
        if profile in kr_by_profile:
            _kr_value_section(pdf, kr_by_profile[profile], label)

    growth = data.get("kr_growth_results", [])
    if growth:
        _kr_growth_section(pdf, growth)

    us = data.get("us_results", [])
    if us:
        _us_section(pdf, us)

    out_path = out_path or (os.path.splitext(path)[0] + ".pdf")
    pdf.output(out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="저장된 스크리닝 리포트(JSON)를 PDF로 내보내기")
    parser.add_argument("--file", type=str, default=None,
                         help="변환할 리포트 파일 경로 (기본: reports/ 안의 가장 최근 파일)")
    parser.add_argument("--out", type=str, default=None,
                         help="저장할 PDF 경로 (기본: 원본 파일명 + .pdf)")
    args = parser.parse_args()

    path = args.file or _latest_report()
    out_path = export(path, args.out)
    print(f"PDF 저장 완료: {out_path}")


if __name__ == "__main__":
    main()
