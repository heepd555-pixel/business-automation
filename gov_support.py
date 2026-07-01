"""
정부 지원사업 통합 수집기
공공데이터포털 공식 API 사용 (합법)
기업마당(소상공인·중소기업·창업) + 복지로(복지·생활) + 고용24(청년·취업)
"""

import os
import json
import csv
import smtplib
import requests
import gspread
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from error_handler import safe_run, send_error_alert

load_dotenv()

PUBLIC_API_KEY  = os.getenv("PUBLIC_DATA_API_KEY")
GMAIL_USER      = os.getenv("GMAIL_USER")
GMAIL_PASSWORD  = os.getenv("GMAIL_PASSWORD")
SHEET_ID        = os.getenv("GOOGLE_SHEET_ID")
CREDS_FILE      = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
CONFIG_FILE     = "gov_설정.json"
SEEN_FILE       = "gov_seen.json"   # 이전 수집 목록 (신규 감지용)

CATEGORY_MAP = {
    "소상공인·중소기업": ["소상공인", "중소기업", "소기업"],
    "청년·취업":        ["청년", "취업", "구직", "일자리"],
    "창업":            ["창업", "벤처", "스타트업"],
    "복지·생활":        ["복지", "생활", "저소득", "장애", "노인", "육아", "출산"],
    "농업·농촌":        ["농업", "농촌", "농어촌", "어업"],
}

# 고용상태별 관련 키워드
EMPLOYMENT_KEYWORDS = {
    "취업준비생": ["취업준비", "구직", "일자리", "취업지원", "청년취업"],
    "재직자":    ["재직자", "근로자", "직장인", "고용유지"],
    "사업자":    ["사업자", "소상공인", "중소기업", "자영업"],
    "프리랜서":  ["프리랜서", "1인", "창작자", "특수고용", "플랫폼종사자", "창업"],
    "무직":      ["실업", "구직", "취업준비", "실직", "고용보험"],
}

# 나이대별 키워드
AGE_KEYWORDS = {
    (15, 34): ["청년", "청소년"],
    (40, 65): ["중장년", "신중년"],
    (65, 99): ["노인", "시니어", "고령"],
}


# ─── 설정 로드 ────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen(ids: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False)


# ─── API 수집 ─────────────────────────────────────────────────

def fetch_bizinfo(page: int = 1, per_page: int = 100) -> list:
    """기업마당 — 소상공인·중소기업·창업 지원사업"""
    try:
        resp = requests.get(
            "https://apis.data.go.kr/B552735/bizinfoService/getOptrPbancList",
            params={
                "serviceKey": PUBLIC_API_KEY,
                "pageNo": page,
                "numOfRows": per_page,
                "returnType": "json",
            },
            timeout=15,
        )
        data = resp.json()
        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        return items if isinstance(items, list) else [items]
    except Exception as e:
        print(f"  [기업마당 오류] {e}")
        return []


def fetch_welfare(page: int = 1, per_page: int = 100) -> list:
    """복지로 — 복지·생활 지원 서비스"""
    try:
        resp = requests.get(
            "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001",
            params={
                "serviceKey": PUBLIC_API_KEY,
                "pageNo": page,
                "numOfRows": per_page,
                "returnType": "json",
            },
            timeout=15,
        )
        data = resp.json()
        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        return items if isinstance(items, list) else [items]
    except Exception as e:
        print(f"  [복지로 오류] {e}")
        return []


def fetch_youth_jobs(page: int = 1, per_page: int = 100) -> list:
    """고용24 — 청년·취업 지원사업"""
    try:
        resp = requests.get(
            "https://apis.data.go.kr/1051000/EmployService/getEmployServiceList",
            params={
                "serviceKey": PUBLIC_API_KEY,
                "pageNo": page,
                "numOfRows": per_page,
                "returnType": "json",
            },
            timeout=15,
        )
        data = resp.json()
        items = (
            data.get("response", {})
                .get("body", {})
                .get("items", {})
                .get("item", [])
        )
        return items if isinstance(items, list) else [items]
    except Exception as e:
        print(f"  [고용24 오류] {e}")
        return []


# ─── 정규화 ───────────────────────────────────────────────────

def normalize_bizinfo(item: dict) -> dict:
    return {
        "ID":       item.get("pbancSn", ""),
        "제목":     item.get("pbancNm", ""),
        "기관":     item.get("insttNm", ""),
        "카테고리": "소상공인·중소기업",
        "지원유형": item.get("sprtTypeNm", ""),
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "URL":      f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pbanc_sn={item.get('pbancSn','')}",
        "출처":     "기업마당",
    }


def normalize_welfare(item: dict) -> dict:
    return {
        "ID":       item.get("serviceId", ""),
        "제목":     item.get("servNm", ""),
        "기관":     item.get("jurMnofNm", ""),
        "카테고리": "복지·생활",
        "지원유형": item.get("lifeNmArray", ""),
        "지역":     item.get("sigunguNm", "전국"),
        "접수시작": "",
        "접수마감": "",
        "URL":      f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={item.get('serviceId','')}",
        "출처":     "복지로",
    }


def normalize_youth(item: dict) -> dict:
    return {
        "ID":       item.get("empSvcId", ""),
        "제목":     item.get("empSvcNm", ""),
        "기관":     item.get("insttNm", ""),
        "카테고리": "청년·취업",
        "지원유형": item.get("empSvcTypNm", ""),
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "URL":      item.get("dtlUrl", ""),
        "출처":     "고용24",
    }


# ─── 필터·분류 ────────────────────────────────────────────────

def detect_category(item: dict) -> str:
    title = item.get("제목", "") + item.get("지원유형", "")
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in title for kw in keywords):
            return cat
    return item.get("카테고리", "기타")


def passes_profile_filter(item: dict, cfg: dict) -> bool:
    """프로필 기반 필터링"""
    profile = cfg.get("내_프로필", {})
    title = item.get("제목", "") + item.get("지원유형", "")

    # 제외 키워드 — 하나라도 포함되면 제외
    for kw in profile.get("제외키워드", []):
        if kw in title:
            return False

    # 관심 키워드 — 입력된 경우 하나라도 포함돼야 통과
    interest = profile.get("관심키워드", [])
    if interest and not any(kw in title for kw in interest):
        # 관심 키워드 없으면 고용상태·나이 키워드로 보완
        pass_by_employment = False
        pass_by_age = False

        # 고용상태 매칭
        employment = profile.get("고용상태", {})
        for status, active in employment.items():
            if active:
                kws = EMPLOYMENT_KEYWORDS.get(status, [])
                if any(kw in title for kw in kws):
                    pass_by_employment = True
                    break

        # 나이 매칭
        age = profile.get("나이", 0)
        if age:
            for (min_age, max_age), kws in AGE_KEYWORDS.items():
                if min_age <= age <= max_age:
                    if any(kw in title for kw in kws):
                        pass_by_age = True
                        break

        if not pass_by_employment and not pass_by_age:
            return False

    # 지역 매칭
    region = profile.get("거주지역", "").strip()
    item_region = item.get("지역", "전국")
    if region and "전국" not in item_region and region not in item_region:
        return False

    return True


def passes_filter(item: dict, cfg: dict) -> bool:
    """프로필 필터 적용"""
    profile = cfg.get("내_프로필", {})

    # 프로필이 비어있으면 전체 수집
    has_profile = (
        profile.get("나이", 0) > 0
        or profile.get("거주지역", "").strip()
        or any(profile.get("고용상태", {}).values())
        or profile.get("관심키워드")
        or profile.get("제외키워드")
    )

    if has_profile:
        return passes_profile_filter(item, cfg)

    return True


def days_until_deadline(item: dict) -> int | None:
    deadline = item.get("접수마감", "")
    if not deadline or len(deadline) < 8:
        return None
    try:
        d = datetime.strptime(deadline[:8], "%Y%m%d")
        return (d - datetime.now()).days
    except ValueError:
        return None


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
            ws.update("A1", [["조건에 맞는 지원사업이 없습니다."]])
            return

        headers = list(results[0].keys())
        rows    = [list(r.values()) for r in results]
        ws.update("A1", [headers] + rows)
        print(f"[Sheets 업데이트] {sheet_name} 완료")
    except Exception as e:
        print(f"[Sheets 오류] {e}")
        send_error_alert("Sheets 업데이트", e)


def send_email_report(results: list, new_items: list, urgent: list, to_email: str):
    try:
        def make_rows(items, limit=10):
            html = ""
            for r in items[:limit]:
                days = days_until_deadline(r)
                days_str = f"D-{days}" if days is not None and days >= 0 else ("마감" if days is not None else "-")
                color = "#ff4444" if days is not None and days <= 3 else (
                        "#ff8800" if days is not None and days <= 7 else "#333")
                html += f"""
                <tr>
                    <td style="padding:6px;border:1px solid #ddd;">{r['카테고리']}</td>
                    <td style="padding:6px;border:1px solid #ddd;">{r['제목'][:40]}</td>
                    <td style="padding:6px;border:1px solid #ddd;">{r['기관']}</td>
                    <td style="padding:6px;border:1px solid #ddd;">{r['지역']}</td>
                    <td style="padding:6px;border:1px solid #ddd;color:{color};font-weight:bold;">{days_str}</td>
                    <td style="padding:6px;border:1px solid #ddd;"><a href="{r['URL']}">바로가기</a></td>
                </tr>"""
            return html

        table_header = """
        <tr style="background:#4472C4;color:white;">
            <th style="padding:6px;">카테고리</th>
            <th style="padding:6px;">사업명</th>
            <th style="padding:6px;">기관</th>
            <th style="padding:6px;">지역</th>
            <th style="padding:6px;">마감</th>
            <th style="padding:6px;">링크</th>
        </tr>"""

        body = f"""
        <h2>정부 지원사업 통합 리포트</h2>
        <p>생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 전체 {len(results)}건</p>
        <hr>

        <h3 style="color:#cc0000;">⚠ 마감 임박 ({len(urgent)}건)</h3>
        <table style="border-collapse:collapse;width:100%">
            {table_header}{make_rows(urgent)}
        </table>

        <h3 style="color:#0066cc;">🆕 신규 등록 ({len(new_items)}건)</h3>
        <table style="border-collapse:collapse;width:100%">
            {table_header}{make_rows(new_items)}
        </table>

        <h3>전체 목록 (상위 20건)</h3>
        <table style="border-collapse:collapse;width:100%">
            {table_header}{make_rows(results, 20)}
        </table>
        """

        msg = MIMEMultipart()
        msg["From"]    = GMAIL_USER
        msg["To"]      = to_email
        msg["Subject"] = f"[정부지원] 마감임박 {len(urgent)}건 · 신규 {len(new_items)}건 — {datetime.now().strftime('%m/%d')}"
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        print(f"[이메일 발송] {to_email}")
    except Exception as e:
        print(f"[이메일 오류] {e}")
        send_error_alert("이메일 리포트", e)


def send_kakao_urgent(urgent: list, phone: str):
    """마감 임박 항목 카카오 알림"""
    from kakao_sender import send_kakao
    for item in urgent[:5]:  # 최대 5건
        days = days_until_deadline(item)
        send_kakao(phone, {
            "사업명": item["제목"][:20],
            "마감일": item["접수마감"],
            "남은일": f"D-{days}",
            "기관":   item["기관"],
        })


# ─── 메인 ─────────────────────────────────────────────────────

def run_gov_support():
    cfg        = load_config()
    seen       = load_seen()
    alert_days = cfg["필터조건"]["마감일_임박_알림_기준(일)"]
    max_count  = cfg["필터조건"]["최대_출력_건수"]
    profile    = cfg.get("내_프로필", {})

    print(f"\n{'='*55}")
    print(f"  정부 지원사업 통합 수집기")
    print(f"  수집 대상: 기업마당 · 복지로 · 고용24")
    print(f"  마감 임박 기준: {alert_days}일 이내")

    # 프로필 요약 출력
    age = profile.get("나이", 0)
    region = profile.get("거주지역", "")
    emp = [k for k, v in profile.get("고용상태", {}).items() if v]
    interests = profile.get("관심키워드", [])
    if age or region or emp or interests:
        print(f"\n  내 프로필")
        if age:      print(f"    나이:     {age}세")
        if region:   print(f"    지역:     {region}")
        if emp:      print(f"    고용상태: {', '.join(emp)}")
        if interests: print(f"    관심키워드: {', '.join(interests)}")
    print(f"{'='*55}\n")

    # 수집
    raw = []
    cat = cfg["필터조건"]["카테고리"]

    if cat.get("소상공인·중소기업") or cat.get("창업") or cat.get("전체"):
        print("  [기업마당] 수집 중...")
        items = fetch_bizinfo(per_page=100)
        raw.extend([normalize_bizinfo(i) for i in items])
        print(f"  → {len(items)}건")

    if cat.get("복지·생활") or cat.get("전체"):
        print("  [복지로] 수집 중...")
        items = fetch_welfare(per_page=100)
        raw.extend([normalize_welfare(i) for i in items])
        print(f"  → {len(items)}건")

    if cat.get("청년·취업") or cat.get("전체"):
        print("  [고용24] 수집 중...")
        items = fetch_youth_jobs(per_page=100)
        raw.extend([normalize_youth(i) for i in items])
        print(f"  → {len(items)}건")

    # 필터
    filtered = [r for r in raw if passes_filter(r, cfg)]

    # 마감일 기준 정렬
    def sort_key(x):
        d = days_until_deadline(x)
        return d if d is not None else 9999

    filtered.sort(key=sort_key)
    filtered = filtered[:max_count]

    # 신규·임박 감지
    new_items = [r for r in filtered if r["ID"] and r["ID"] not in seen]
    urgent    = [r for r in filtered
                 if (d := days_until_deadline(r)) is not None and 0 <= d <= alert_days]

    print(f"\n  전체: {len(filtered)}건 | 신규: {len(new_items)}건 | 마감임박: {len(urgent)}건\n")

    # 임박 목록 출력
    if urgent:
        print(f"  ⚠ 마감 임박 ({alert_days}일 이내)")
        for r in urgent:
            d = days_until_deadline(r)
            print(f"    D-{d:>2} | {r['카테고리']:<12} | {r['제목'][:35]}")

    # CSV
    if cfg["출력설정"]["CSV저장"]:
        filename = f"정부지원_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        save_csv(filtered, filename)

    # Google Sheets
    if cfg["출력설정"]["Google_Sheets_업데이트"]:
        update_sheets(filtered, cfg["Google_Sheets설정"]["시트명"])

    # 이메일
    if cfg["출력설정"]["이메일_리포트_발송"]:
        to = cfg["이메일설정"]["수신_이메일"]
        if to:
            send_email_report(filtered, new_items, urgent, to)

    # 카카오
    if cfg["출력설정"]["카카오_마감임박_알림"] and urgent:
        phone = cfg["카카오설정"]["수신_전화번호"]
        if phone:
            send_kakao_urgent(urgent, phone)

    # seen 업데이트
    new_ids = {r["ID"] for r in filtered if r["ID"]}
    save_seen(seen | new_ids)

    print(f"\n{'='*55}")
    print(f"  완료")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    safe_run("정부 지원사업 수집기", run_gov_support)
