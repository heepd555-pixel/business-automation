"""
DART 재무 스크리너 — 판매용
opendart.fss.or.kr 공식 API 사용 (합법)
투자 추천이 아닌 재무 데이터 필터링 도구입니다.
"""

import os
import json
import time
import csv
import smtplib
import requests
import gspread
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from error_handler import safe_run, send_error_alert

load_dotenv()

DART_API_KEY  = os.getenv("DART_API_KEY")
GMAIL_USER    = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
SHEET_ID      = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE    = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
BASE_URL      = "https://opendart.fss.or.kr/api"
CONFIG_FILE   = "dart_설정.json"


# ─── 설정 로드 ────────────────────────────────────────────────

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        print(f"[오류] {CONFIG_FILE} 파일이 없습니다.")
        raise FileNotFoundError(CONFIG_FILE)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── 데이터 수집 ──────────────────────────────────────────────

def get_corp_list() -> list:
    """KOSPI + KOSDAQ 전체 상장사 목록"""
    corps = []
    for market in ["Y", "K"]:
        page = 1
        while True:
            resp = requests.get(
                f"{BASE_URL}/list.json",
                params={
                    "crtfc_key": DART_API_KEY,
                    "listed_at": market,
                    "page_count": 100,
                    "page_no": page,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("status") != "000":
                break
            items = data.get("list", [])
            corps.extend(items)
            if len(items) < 100:
                break
            page += 1
    print(f"[수집 완료] 상장사 {len(corps)}개")
    return corps


def get_financial_items(corp_code: str, year: str) -> list | None:
    """연결→별도 순으로 재무제표 수집"""
    for fs_div in ["CFS", "OFS"]:
        resp = requests.get(
            f"{BASE_URL}/fnlttSinglAcntAll.json",
            params={
                "crtfc_key": DART_API_KEY,
                "corp_code": corp_code,
                "bsns_year": year,
                "reprt_code": "11011",
                "fs_div": fs_div,
            },
            timeout=10,
        )
        data = resp.json()
        if data.get("status") == "000":
            return data.get("list", [])
    return None


# ─── 지표 계산 ────────────────────────────────────────────────

def parse_amount(value) -> float:
    try:
        return float(str(value).replace(",", "").replace(" ", "") or 0)
    except (ValueError, TypeError):
        return 0.0


def extract_metrics(items: list) -> dict:
    data = {}
    for item in items:
        acct = item.get("account_nm", "")
        amt  = parse_amount(item.get("thstrm_amount", 0))
        prev = parse_amount(item.get("frmtrm_amount", 0))

        if "매출액" in acct and "영업" not in acct and "revenue" not in data:
            data["revenue"] = amt
            data["prev_revenue"] = prev
        elif acct == "영업이익":
            data["operating_income"] = amt
        elif "당기순이익" in acct and "지배" not in acct and "net_income" not in data:
            data["net_income"] = amt
        elif "자본총계" in acct and "equity" not in data:
            data["equity"] = amt
        elif "부채총계" in acct and "total_debt" not in data:
            data["total_debt"] = amt
        elif "자산총계" in acct and "total_assets" not in data:
            data["total_assets"] = amt

    return data


def calculate_ratios(m: dict) -> dict:
    revenue   = m.get("revenue", 0)
    prev_rev  = m.get("prev_revenue", 0)
    op_income = m.get("operating_income", 0)
    net_income = m.get("net_income", 0)
    equity    = m.get("equity", 1) or 1
    debt      = m.get("total_debt", 0)

    return {
        "ROE(%)":        round(net_income / equity * 100, 2),
        "부채비율(%)":   round(debt / equity * 100, 2),
        "영업이익률(%)": round(op_income / revenue * 100, 2) if revenue else 0,
        "매출성장률(%)": round((revenue - prev_rev) / abs(prev_rev) * 100, 2) if prev_rev else 0,
        "매출액(억)":    round(revenue / 1e8, 1),
        "영업이익(억)":  round(op_income / 1e8, 1),
        "순이익(억)":    round(net_income / 1e8, 1),
    }


def passes_filter(ratios: dict, cfg: dict) -> bool:
    f = cfg["필터조건"]
    return (
        ratios["ROE(%)"]        >= f["ROE_최소(%)"]
        and ratios["부채비율(%)"]   <= f["부채비율_최대(%)"]
        and ratios["매출성장률(%)"] >= f["매출성장률_최소(%)"]
        and ratios["영업이익률(%)"] >= f["영업이익률_최소(%)"]
        and ratios["매출액(억)"]    >= f["매출액_최소(억원)"]
    )


# ─── 출력 ─────────────────────────────────────────────────────

def save_csv(results: list, filename: str):
    if not results:
        return
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"[CSV 저장] {filename}")


def update_sheets(results: list, sheet_name: str):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds  = Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)
        client = gspread.authorize(creds)
        wb     = client.open_by_key(SHEET_ID)

        try:
            ws = wb.worksheet(sheet_name)
            ws.clear()
        except gspread.WorksheetNotFound:
            ws = wb.add_worksheet(title=sheet_name, rows=500, cols=15)

        if not results:
            ws.update("A1", [["조건에 맞는 기업이 없습니다."]])
            return

        headers = list(results[0].keys())
        rows    = [list(r.values()) for r in results]
        ws.update("A1", [headers] + rows)
        print(f"[Sheets 업데이트] {sheet_name} 시트 완료")
    except Exception as e:
        print(f"[Sheets 오류] {e}")
        send_error_alert("Sheets 업데이트", e)


def send_email_report(results: list, to_email: str, year: str, cfg: dict):
    try:
        f = cfg["필터조건"]
        top = results[:10]

        rows_html = ""
        for i, r in enumerate(top, 1):
            rows_html += f"""
            <tr>
                <td style="padding:6px;border:1px solid #ddd;">{i}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['기업명']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['종목코드']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['ROE(%)']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['부채비율(%)']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['영업이익률(%)']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['매출성장률(%)']}</td>
                <td style="padding:6px;border:1px solid #ddd;">{r['매출액(억)']}</td>
            </tr>"""

        body = f"""
        <h2>DART 재무 스크리닝 리포트</h2>
        <p>기준연도: {year}년 | 생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <hr>
        <h3>적용 필터 조건</h3>
        <ul>
            <li>ROE: {f['ROE_최소(%)']}% 이상</li>
            <li>부채비율: {f['부채비율_최대(%)']}% 이하</li>
            <li>매출성장률: {f['매출성장률_최소(%)']}% 이상</li>
            <li>영업이익률: {f['영업이익률_최소(%)']}% 이상</li>
            <li>매출액: {f['매출액_최소(억원)']}억원 이상</li>
        </ul>
        <h3>결과: 총 {len(results)}개 기업 (상위 10개 표시)</h3>
        <table style="border-collapse:collapse;width:100%">
            <tr style="background:#4472C4;color:white;">
                <th style="padding:6px;border:1px solid #ddd;">순위</th>
                <th style="padding:6px;border:1px solid #ddd;">기업명</th>
                <th style="padding:6px;border:1px solid #ddd;">종목코드</th>
                <th style="padding:6px;border:1px solid #ddd;">ROE(%)</th>
                <th style="padding:6px;border:1px solid #ddd;">부채비율(%)</th>
                <th style="padding:6px;border:1px solid #ddd;">영업이익률(%)</th>
                <th style="padding:6px;border:1px solid #ddd;">매출성장률(%)</th>
                <th style="padding:6px;border:1px solid #ddd;">매출액(억)</th>
            </tr>
            {rows_html}
        </table>
        <br>
        <p style="color:#888;font-size:12px;">
        ※ 본 리포트는 DART 공시 재무데이터를 자동 수집·필터링한 결과입니다.<br>
        투자 추천이 아니며 투자 판단은 본인 책임 하에 이루어져야 합니다.
        </p>
        """

        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email
        msg["Subject"] = f"[DART 스크리닝] {year}년 재무 필터링 결과 — {len(results)}개 기업"
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"[이메일 발송] {to_email}")
    except Exception as e:
        print(f"[이메일 오류] {e}")
        send_error_alert("이메일 리포트 발송", e)


# ─── 메인 ─────────────────────────────────────────────────────

def run_screener():
    cfg  = load_config()
    year = cfg.get("분석_기준연도", str(datetime.now().year - 1))
    f    = cfg["필터조건"]
    sort_key   = cfg["정렬기준"]["기준"]
    sort_desc  = cfg["정렬기준"]["내림차순"]
    max_output = cfg["출력설정"]["최대_출력_기업수"]

    sort_map = {
        "ROE":        "ROE(%)",
        "매출성장률":  "매출성장률(%)",
        "영업이익률":  "영업이익률(%)",
        "부채비율":    "부채비율(%)",
    }
    sort_col = sort_map.get(sort_key, "ROE(%)")

    print(f"\n{'='*55}")
    print(f"  DART 재무 스크리너  ({year}년 기준)")
    print(f"  ROE≥{f['ROE_최소(%)']}%  부채비율≤{f['부채비율_최대(%)']}%")
    print(f"  매출성장률≥{f['매출성장률_최소(%)']}%  영업이익률≥{f['영업이익률_최소(%)']}%")
    print(f"  매출액≥{f['매출액_최소(억원)']}억  정렬: {sort_key}")
    print(f"{'='*55}\n")

    corps = get_corp_list()
    if not corps:
        print("[오류] 기업 목록 수집 실패. DART_API_KEY 확인 필요")
        return

    results = []
    fail_count = 0

    for i, corp in enumerate(corps):
        corp_code = corp.get("corp_code")
        corp_name = corp.get("corp_name", "")
        stock_code = corp.get("stock_code", "")

        try:
            items = get_financial_items(corp_code, year)
            if not items:
                continue

            metrics = extract_metrics(items)
            if not metrics.get("revenue"):
                continue

            ratios = calculate_ratios(metrics)

            if passes_filter(ratios, cfg):
                results.append({
                    "기업명":        corp_name,
                    "종목코드":      stock_code,
                    **ratios,
                    "수집일":        datetime.now().strftime("%Y-%m-%d"),
                })
                print(f"  ✅ {corp_name:<15} ROE {ratios['ROE(%)']:>7}%  "
                      f"부채비율 {ratios['부채비율(%)']:>7}%  "
                      f"성장률 {ratios['매출성장률(%)']:>7}%")

            if i % 10 == 0:
                time.sleep(0.3)

        except Exception as e:
            fail_count += 1
            continue

    # 정렬
    results.sort(key=lambda x: x.get(sort_col, 0), reverse=sort_desc)
    results = results[:max_output]

    print(f"\n{'='*55}")
    print(f"  완료: {len(corps)}개 분석 | {len(results)}개 선별 | {fail_count}개 수집실패")
    print(f"{'='*55}\n")

    # CSV 저장
    if cfg["출력설정"]["CSV저장"]:
        filename = f"스크리닝_{year}_{datetime.now().strftime('%m%d_%H%M')}.csv"
        save_csv(results, filename)

    # Google Sheets 업데이트
    if cfg["출력설정"]["Google_Sheets_업데이트"]:
        update_sheets(results, cfg["Google_Sheets설정"]["시트명"])

    # 이메일 발송
    if cfg["출력설정"]["이메일_리포트_발송"]:
        to_email = cfg["이메일설정"]["수신_이메일"]
        if to_email:
            send_email_report(results, to_email, year, cfg)
        else:
            print("[이메일 건너뜀] 수신_이메일이 비어 있습니다.")


if __name__ == "__main__":
    safe_run("DART 재무 스크리너", run_screener)
