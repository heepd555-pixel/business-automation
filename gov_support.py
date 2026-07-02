"""
정부 지원사업 통합 수집기
공공데이터포털 공식 API 사용 (합법)
기업마당 + K-스타트업 + 소진공 + 복지로 + 고용24 + 농림부
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

# 복지로 지원서비스 세부 분류
WELFARE_SUBCATEGORY = {
    "생계지원": [
        "생계급여", "긴급복지", "긴급생계", "식품지원",
        "푸드뱅크", "에너지바우처", "냉난방", "연료비",
        "이웃돕기", "긴급지원",
    ],
    "주거지원": [
        "주거급여", "전세자금", "월세지원", "주거비",
        "주택개보수", "임시주거", "쉼터", "공공임대",
        "주거취약", "전월세",
    ],
    "의료·건강": [
        "의료급여", "건강보험", "의료비지원", "치료비",
        "재활", "정신건강", "정신질환", "희귀질환",
        "암검진", "건강검진", "치과", "한방",
    ],
    "교육·보육": [
        "교육급여", "보육료", "양육수당", "아동수당",
        "교육비지원", "학습지원", "방과후", "돌봄",
        "급식지원", "교육청", "학교", "장학금",
    ],
    "노인·경로": [
        "기초연금", "노인일자리", "치매", "독거노인",
        "노인복지", "경로당", "노인돌봄", "재가서비스",
        "방문간호", "노인인지", "노인학대",
    ],
    "장애인": [
        "장애인연금", "장애수당", "활동지원", "보조기기",
        "발달재활", "언어치료", "장애아동", "장애인취업",
        "장애인주거", "장애인의료", "중증장애",
    ],
    "임신·출산": [
        "임산부", "임신", "출산지원", "산모신생아",
        "난임시술", "난임지원", "출산장려금", "첫만남이용권",
        "임신출산진료비", "산후조리",
    ],
    "아동·청소년": [
        "아동수당", "드림스타트", "지역아동센터",
        "청소년지원", "청소년쉼터", "학교밖청소년",
        "아동급식", "아동보호", "가정위탁",
    ],
    "한부모·다문화": [
        "한부모", "미혼모", "미혼부", "양육비",
        "다문화가족", "결혼이민자", "이주여성",
        "가족센터", "다문화교육",
    ],
    "자활·사회참여": [
        "자활사업", "자활기업", "근로능력",
        "자원봉사", "사회참여", "노인사회활동",
        "노인자원봉사", "봉사활동",
    ],
}

# 고용24 취업지원 세부 분류
EMPLOYMENT_SUBCATEGORY = {
    "청년취업": [
        "청년", "청년도약", "청년내일저축", "청년구직활동지원금",
        "청년취업사관학교", "청년일경험", "청년월세", "청년저축",
        "청년인턴", "청년고용",
    ],
    "중장년취업": [
        "중장년", "신중년", "재취직", "중장년내일센터",
        "신중년경력형", "퇴직자", "장년", "50대", "60대",
    ],
    "장애인고용": [
        "장애인취업", "장애인고용", "장애인고용장려금",
        "보조공학", "장애인직업훈련", "장애인인턴",
        "중증장애인지원고용",
    ],
    "여성취업": [
        "경력단절", "경단녀", "새일센터", "여성취업",
        "여성가장", "직장어린이집", "출산후재취업",
        "여성고용",
    ],
    "취업지원서비스": [
        "취업성공패키지", "국민취업지원제도",
        "구직급여", "취업지원", "고용센터",
        "취업상담", "직업진로", "취업알선",
    ],
    "직업훈련": [
        "국민내일배움카드", "내일배움카드", "직업훈련",
        "K-디지털", "산업전환훈련", "사업주훈련",
        "직업능력", "기술훈련", "직무교육",
    ],
    "고용장려·일자리창출": [
        "고용장려금", "일자리창출", "지역일자리",
        "사회적일자리", "공공일자리", "노인일자리",
        "청년일자리", "사회서비스일자리",
    ],
    "실업급여·소득지원": [
        "실업급여", "구직급여", "조기재취업수당",
        "연장급여", "훈련연장급여", "개별연장급여",
    ],
    "특수고용·플랫폼": [
        "특수고용", "특수형태근로", "플랫폼종사자",
        "프리랜서", "1인사업자", "예술인고용보험",
        "노무제공자",
    ],
    "외국인·다문화취업": [
        "고용허가제", "외국인근로자", "다문화취업",
        "결혼이민자취업", "이주민고용",
    ],
}

# 농업·농촌 지원사업 세부 분류
AGRICULTURE_SUBCATEGORY = {
    "귀농·귀촌": [
        "귀농", "귀촌", "귀어", "귀산촌",
        "귀농창업", "귀농교육", "귀농정착",
        "영농정착지원금", "청년농부",
    ],
    "스마트팜·첨단농업": [
        "스마트팜", "스마트온실", "스마트축산",
        "첨단농업", "ICT농업", "드론방제",
        "농업데이터", "디지털농업",
    ],
    "영농자금·융자": [
        "농업자금", "영농자금", "농신보",
        "농업정책자금", "영농재해", "피해복구자금",
        "농업경영체", "농지은행",
    ],
    "직불금·보조금": [
        "직불금", "공익직불", "친환경직불",
        "쌀직불", "밭직불", "농업보조금",
        "농업지원금", "경영안정",
    ],
    "농산물판로·수출": [
        "농산물판로", "농산물수출", "로컬푸드",
        "직거래장터", "온라인판매", "농식품수출",
        "6차산업", "농촌융복합",
    ],
    "축산·어업": [
        "축산", "가축", "어업", "수산",
        "어가", "어촌", "수산자원",
        "어업인", "양식",
    ],
    "농촌복지·생활": [
        "농촌복지", "농업인건강보험", "농업인연금",
        "농촌마을", "농촌주거", "농업인안전",
        "농업재해보험",
    ],
    "교육·컨설팅": [
        "농업교육", "영농교육", "농촌체험",
        "농업컨설팅", "농업기술", "농촌진흥",
        "품목별기술", "농업연구",
    ],
}

# 중소벤처기업부 지원사업 세부 분류
SME_SUBCATEGORY = {
    "정책자금·융자": [
        "정책자금", "융자", "대출", "보증",
        "창업기업지원자금", "신성장기반자금",
        "긴급경영안정자금", "소상공인정책자금",
        "특별경영안정자금", "혁신창업사업화자금",
    ],
    "보조금·지원금": [
        "보조금", "지원금", "바우처", "지원사업",
        "사업화자금", "지원비용", "수당",
    ],
    "창업지원": [
        "예비창업패키지", "초기창업패키지", "창업도약패키지",
        "창업성장기술개발", "TIPS", "팁스",
        "창업도전500", "글로벌창업", "창업인프라",
        "창업보육센터", "액셀러레이터",
        "창업경진대회", "창업지원센터",
    ],
    "기술개발·R&D": [
        "기술개발", "R&D", "연구개발", "기술혁신",
        "중소기업기술개발", "혁신형중소기업",
        "IP나래", "기술보호", "특허",
    ],
    "수출·판로": [
        "수출바우처", "수출지원", "해외판로",
        "내수기업수출", "글로벌마케팅",
        "해외전시", "온라인수출", "직구역직구",
        "수출컨소시엄", "해외지사화",
    ],
    "스마트화·디지털": [
        "스마트공장", "스마트상점", "스마트공방",
        "디지털전환", "AI도입", "자동화",
        "스마트제조", "클라우드", "빅데이터",
    ],
    "소상공인특화": [
        "소상공인", "자영업", "영세", "골목상권",
        "노란우산공제", "재도전", "폐업지원",
        "경영개선", "컨설팅", "점포환경개선",
        "협업활성화", "공동브랜드",
    ],
    "인력·교육": [
        "인력지원", "채용지원", "청년일자리",
        "내일채움공제", "청년재직자", "인력양성",
        "직업훈련", "역량강화", "멘토링",
    ],
    "투자·IR": [
        "투자연계", "엔젤투자", "벤처투자",
        "크라우드펀딩", "IR지원", "투자유치",
        "성장사다리", "모태펀드",
    ],
    "인증·컨설팅": [
        "이노비즈", "메인비즈", "벤처인증",
        "경영컨설팅", "진단", "멘토링",
        "ISO인증", "품질경영",
    ],
}

# 프로필 항목별 매칭 키워드
PROFILE_KEYWORDS = {
    # 고용상태
    "취업준비생":   ["취업준비", "구직", "일자리", "취업지원", "청년취업", "취업성공"],
    "재직자":       ["재직자", "근로자", "직장인", "고용유지", "근무중"],
    "사업자":       ["사업자", "소상공인", "중소기업", "자영업", "소기업"],
    "프리랜서":     ["프리랜서", "1인", "특수고용", "플랫폼종사자", "독립계약자"],
    "무직":         ["실업", "구직", "실직", "비경제활동"],
    "경력단절":     ["경력단절", "경단녀", "재취업", "새일"],
    "육아휴직중":   ["육아휴직", "출산휴가", "모성보호"],
    "퇴직자":       ["퇴직", "명예퇴직", "조기퇴직", "중장년"],

    # 나이대
    "청소년(15-18)": ["청소년", "고등학생"],
    "청년(19-34)":   ["청년", "청년층", "청년지원"],
    "중장년(40-64)": ["중장년", "신중년", "중년"],
    "노인(65+)":     ["노인", "어르신", "시니어", "고령자", "노년"],

    # 성별
    "여성":          ["여성", "여성기업", "경단녀", "모성", "임산부", "산모", "육아"],
    "남성":          ["남성", "부성", "아버지"],

    # 가족상황
    "임신여부":      ["임산부", "임신", "출산", "산모", "태아"],
    "한부모가족":    ["한부모", "모자가정", "부자가정", "미혼모", "미혼부"],
    "조손가족":      ["조손", "조부모", "손자"],
    "다문화가족":    ["다문화", "결혼이민자", "외국인배우자"],
    "다자녀":        ["다자녀", "셋째", "다둥이", "출산장려"],
    "영아(0-2세)":   ["영아", "신생아", "0세", "1세", "2세", "영유아"],
    "유아(3-7세)":   ["유아", "어린이집", "유치원", "보육"],
    "초등(8-13세)":  ["초등학생", "방과후", "돌봄"],
    "청소년자녀":    ["청소년자녀", "중고등학생"],

    # 주거
    "무주택":        ["무주택", "전세", "월세", "주거취약", "청약"],
    "기초수급자":    ["기초생활", "수급자", "생계급여", "의료급여"],
    "차상위계층":    ["차상위", "저소득", "취약계층"],

    # 건강·장애
    "장애인":        ["장애인", "장애", "장애우", "장애등급"],
    "만성질환":      ["만성질환", "고혈압", "당뇨", "암환자", "희귀질환"],
    "국가유공자":    ["국가유공자", "보훈", "참전"],

    # 학력·교육
    "국비교육":      ["국비", "직업훈련", "내일배움카드", "훈련수당"],
    "재학중":        ["재학생", "대학생", "재학"],

    # 사업·창업
    "예비창업":      ["예비창업", "창업준비", "창업희망"],
    "초기창업":      ["초기창업", "창업 1년", "창업 2년", "창업 3년"],
    "소상공인":      ["소상공인", "영세", "자영업자"],
    "여성기업인":    ["여성기업", "여성창업", "여성사업"],
    "농어업인":      ["농업인", "어업인", "농어민", "귀농"],

    # 특수상황
    "북한이탈주민":  ["탈북", "북한이탈", "새터민"],
    "사회적기업":    ["사회적기업", "협동조합", "사회혁신"],
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

def _get_items(url: str, params: dict, path: list, label: str) -> list:
    """공통 API 호출 헬퍼"""
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        for key in path:
            data = data.get(key, {})
        items = data if isinstance(data, list) else ([data] if data else [])
        return items
    except Exception as e:
        print(f"  [{label} 오류] {e}")
        return []


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


def fetch_kstartup(page: int = 1, per_page: int = 100) -> list:
    """창업진흥원 K-스타트업 — 창업 지원사업"""
    return _get_items(
        "https://apis.data.go.kr/B553077/strtpSportBizInfoService/getStrtpSportBizInfoList",
        {
            "serviceKey": PUBLIC_API_KEY,
            "pageNo": page,
            "numOfRows": per_page,
            "returnType": "json",
        },
        ["response", "body", "items", "item"],
        "K-스타트업",
    )


def fetch_smes_fund(page: int = 1, per_page: int = 100) -> list:
    """중소벤처기업부 정책자금 — 융자·보조금"""
    return _get_items(
        "https://apis.data.go.kr/B552735/bizinfoService/getSmeFundList",
        {
            "serviceKey": PUBLIC_API_KEY,
            "pageNo": page,
            "numOfRows": per_page,
            "returnType": "json",
        },
        ["response", "body", "items", "item"],
        "중기부 정책자금",
    )


def fetch_soss(page: int = 1, per_page: int = 100) -> list:
    """소상공인시장진흥공단 — 소상공인 지원사업"""
    return _get_items(
        "https://apis.data.go.kr/B552735/bizinfoService/getSossSupportList",
        {
            "serviceKey": PUBLIC_API_KEY,
            "pageNo": page,
            "numOfRows": per_page,
            "returnType": "json",
        },
        ["response", "body", "items", "item"],
        "소진공",
    )


def fetch_agriculture(page: int = 1, per_page: int = 100) -> list:
    """농림축산식품부 — 농업·농촌 지원사업 (기업마당 농업 카테고리)"""
    return _get_items(
        "https://apis.data.go.kr/B552735/bizinfoService/getOptrPbancList",
        {
            "serviceKey": PUBLIC_API_KEY,
            "pageNo": page,
            "numOfRows": per_page,
            "returnType": "json",
            "suportType": "농업",
        },
        ["response", "body", "items", "item"],
        "농업지원",
    )


def fetch_youth_jobs_additional(page: int = 1, per_page: int = 100) -> list:
    """고용24 추가 — 중장년·특수고용 지원사업"""
    return _get_items(
        "https://apis.data.go.kr/1051000/EmployService/getEmployServiceList",
        {
            "serviceKey": PUBLIC_API_KEY,
            "pageNo": page + 1,
            "numOfRows": per_page,
            "returnType": "json",
        },
        ["response", "body", "items", "item"],
        "고용24(2페이지)",
    )


# ─── 정규화 ───────────────────────────────────────────────────

def _detect_subcategory(text: str, category_dict: dict, default: str = "기타") -> str:
    for sub, keywords in category_dict.items():
        if any(kw in text for kw in keywords):
            return sub
    return default


def detect_sme_subcategory(title: str, support_type: str) -> str:
    return _detect_subcategory(title + support_type, SME_SUBCATEGORY, "기타지원")


def detect_welfare_subcategory(title: str, life_category: str) -> str:
    return _detect_subcategory(title + life_category, WELFARE_SUBCATEGORY, "기타복지")


def detect_employment_subcategory(title: str, emp_type: str) -> str:
    return _detect_subcategory(title + emp_type, EMPLOYMENT_SUBCATEGORY, "기타취업지원")


def detect_agriculture_subcategory(title: str, support_type: str) -> str:
    return _detect_subcategory(title + support_type, AGRICULTURE_SUBCATEGORY, "기타농업지원")


def normalize_bizinfo(item: dict) -> dict:
    title   = item.get("pbancNm", "")
    sp_type = item.get("sprtTypeNm", "")
    return {
        "ID":       item.get("pbancSn", ""),
        "제목":     title,
        "기관":     item.get("insttNm", ""),
        "카테고리": "소상공인·중소기업",
        "세부분류": detect_sme_subcategory(title, sp_type),
        "지원유형": sp_type,
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "지원규모": item.get("sprtScaleNm", ""),
        "URL":      f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pbanc_sn={item.get('pbancSn','')}",
        "출처":     "기업마당",
    }


def normalize_kstartup(item: dict) -> dict:
    title = item.get("bizPbancNm", "")
    return {
        "ID":       item.get("bizPbancSn", ""),
        "제목":     title,
        "기관":     item.get("supOrgnNm", "창업진흥원"),
        "카테고리": "창업",
        "세부분류": detect_sme_subcategory(title, ""),
        "지원유형": item.get("bizPbancTypNm", ""),
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("pbancBgngYmd", ""),
        "접수마감": item.get("pbancEndYmd", ""),
        "지원규모": item.get("sprtScaleNm", ""),
        "URL":      f"https://www.k-startup.go.kr/web/contents/bizpbanc-ongoing.do",
        "출처":     "K-스타트업",
    }


def normalize_soss(item: dict) -> dict:
    title = item.get("pbancNm", "")
    return {
        "ID":       item.get("pbancSn", ""),
        "제목":     title,
        "기관":     item.get("insttNm", "소상공인시장진흥공단"),
        "카테고리": "소상공인·중소기업",
        "세부분류": detect_sme_subcategory(title, "소상공인"),
        "지원유형": item.get("sprtTypeNm", ""),
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "지원규모": item.get("sprtScaleNm", ""),
        "URL":      "https://www.semas.or.kr/web/SUB03/subpage03.kmdc",
        "출처":     "소진공",
    }


def normalize_welfare(item: dict) -> dict:
    title       = item.get("servNm", "")
    life_cat    = item.get("lifeNmArray", "")
    target_grp  = item.get("trgterIndvdlNm", "")  # 복지로 지원대상
    return {
        "ID":       item.get("serviceId", ""),
        "제목":     title,
        "기관":     item.get("jurMnofNm", ""),
        "카테고리": "복지·생활",
        "세부분류": detect_welfare_subcategory(title, life_cat + target_grp),
        "지원유형": life_cat,
        "지원대상": target_grp,
        "지역":     item.get("sigunguNm", "전국"),
        "접수시작": item.get("alwServBgngYmd", ""),
        "접수마감": item.get("alwServEndYmd", ""),
        "지원규모": item.get("srvAmt", ""),
        "URL":      f"https://www.bokjiro.go.kr/ssis-tbu/twataa/wlfareInfo/moveTWAT52011M.do?wlfareInfoId={item.get('serviceId','')}",
        "출처":     "복지로",
    }


def normalize_youth(item: dict) -> dict:
    title    = item.get("empSvcNm", "")
    emp_type = item.get("empSvcTypNm", "")
    target   = item.get("trgterNm", "")      # 고용24 지원대상
    return {
        "ID":       item.get("empSvcId", ""),
        "제목":     title,
        "기관":     item.get("insttNm", ""),
        "카테고리": "청년·취업",
        "세부분류": detect_employment_subcategory(title, emp_type + target),
        "지원유형": emp_type,
        "지원대상": target,
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "지원규모": item.get("sprtScaleNm", ""),
        "URL":      item.get("dtlUrl", ""),
        "출처":     "고용24",
    }


def normalize_agriculture(item: dict) -> dict:
    title   = item.get("pbancNm", "")
    sp_type = item.get("sprtTypeNm", "")
    return {
        "ID":       item.get("pbancSn", ""),
        "제목":     title,
        "기관":     item.get("insttNm", ""),
        "카테고리": "농업·농촌",
        "세부분류": detect_agriculture_subcategory(title, sp_type),
        "지원유형": sp_type,
        "지원대상": item.get("trgterNm", "농업인"),
        "지역":     item.get("ctpvNm", "전국"),
        "접수시작": item.get("rcptBgngYmd", ""),
        "접수마감": item.get("rcptEndYmd", ""),
        "지원규모": item.get("sprtScaleNm", ""),
        "URL":      f"https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pbanc_sn={item.get('pbancSn','')}",
        "출처":     "농림부(기업마당)",
    }


# ─── 필터·분류 ────────────────────────────────────────────────

def detect_category(item: dict) -> str:
    title = item.get("제목", "") + item.get("지원유형", "")
    for cat, keywords in CATEGORY_MAP.items():
        if any(kw in title for kw in keywords):
            return cat
    return item.get("카테고리", "기타")


def build_active_keywords(profile: dict) -> list:
    """프로필에서 활성화된 키워드 목록 추출"""
    active = []
    기본 = profile.get("기본정보", {})
    가족 = profile.get("가족상황", {})
    고용 = profile.get("고용소득", {})
    건강 = profile.get("건강장애", {})
    주거 = profile.get("주거상황", {})
    학력 = profile.get("학력교육", {})
    사업 = profile.get("사업창업", {})
    특수 = profile.get("특수상황", {})

    # 나이대
    age = 기본.get("나이", 0)
    if age:
        if 15 <= age <= 18: active += PROFILE_KEYWORDS["청소년(15-18)"]
        if 19 <= age <= 34: active += PROFILE_KEYWORDS["청년(19-34)"]
        if 40 <= age <= 64: active += PROFILE_KEYWORDS["중장년(40-64)"]
        if age >= 65:       active += PROFILE_KEYWORDS["노인(65+)"]

    # 성별
    gender = 기본.get("성별", "")
    if gender == "여성": active += PROFILE_KEYWORDS["여성"]
    if gender == "남성": active += PROFILE_KEYWORDS["남성"]

    # 가족상황
    if 가족.get("임신여부"):      active += PROFILE_KEYWORDS["임신여부"]
    if 가족.get("한부모가족"):    active += PROFILE_KEYWORDS["한부모가족"]
    if 가족.get("조손가족"):      active += PROFILE_KEYWORDS["조손가족"]
    if 가족.get("다문화가족"):    active += PROFILE_KEYWORDS["다문화가족"]
    if 가족.get("자녀수", 0) >= 3: active += PROFILE_KEYWORDS["다자녀"]
    for 나이대 in 가족.get("자녀나이대", []):
        if 나이대 in PROFILE_KEYWORDS:
            active += PROFILE_KEYWORDS[나이대]

    # 고용상태
    emp = 고용.get("고용상태", {})
    for status, active_flag in emp.items():
        if active_flag and status in PROFILE_KEYWORDS:
            active += PROFILE_KEYWORDS[status]

    # 소득 기준 (중위소득)
    income = 고용.get("월소득(만원)", 0)
    if income and income <= 111:  active += ["기초생활", "수급자"]
    elif income and income <= 222: active += ["저소득", "차상위"]

    # 건강·장애
    if 건강.get("장애인등록"):   active += PROFILE_KEYWORDS["장애인"]
    if 건강.get("만성질환보유"): active += PROFILE_KEYWORDS["만성질환"]
    if 건강.get("국가유공자"):   active += PROFILE_KEYWORDS["국가유공자"]

    # 주거
    if 주거.get("무주택"):         active += PROFILE_KEYWORDS["무주택"]
    if 주거.get("기초생활수급자"): active += PROFILE_KEYWORDS["기초수급자"]
    if 주거.get("차상위계층"):     active += PROFILE_KEYWORDS["차상위계층"]

    # 학력·교육
    if 학력.get("국비교육수강중"): active += PROFILE_KEYWORDS["국비교육"]
    if 학력.get("재학중"):         active += PROFILE_KEYWORDS["재학중"]

    # 사업·창업
    if 사업.get("예비창업자"):   active += PROFILE_KEYWORDS["예비창업"]
    if 사업.get("소상공인"):     active += PROFILE_KEYWORDS["소상공인"]
    if 사업.get("여성기업인"):   active += PROFILE_KEYWORDS["여성기업인"]
    창업연차 = 사업.get("창업연차", 0)
    if 0 < 창업연차 <= 3:        active += PROFILE_KEYWORDS["초기창업"]

    # 특수상황
    if 특수.get("북한이탈주민"): active += PROFILE_KEYWORDS["북한이탈주민"]
    if 특수.get("농어업인"):     active += PROFILE_KEYWORDS["농어업인"]
    if 특수.get("사회적기업운영"): active += PROFILE_KEYWORDS["사회적기업"]

    # 관심 키워드 직접 추가
    active += profile.get("관심키워드", [])

    return list(set(active))


def passes_profile_filter(item: dict, profile: dict) -> bool:
    """프로필 기반 필터링"""
    title = item.get("제목", "") + item.get("지원유형", "")

    # 제외 키워드
    for kw in profile.get("제외키워드", []):
        if kw in title:
            return False

    # 지역 매칭
    region = profile.get("기본정보", {}).get("거주지역", "").strip()
    item_region = item.get("지역", "전국")
    if region and "전국" not in item_region and region not in item_region:
        return False

    # 활성 키워드 매칭
    active_kws = build_active_keywords(profile)
    if active_kws and not any(kw in title for kw in active_kws):
        return False

    return True


def passes_filter(item: dict, cfg: dict) -> bool:
    profile = cfg.get("내_프로필", {})
    기본 = profile.get("기본정보", {})
    고용 = profile.get("고용소득", {})

    has_profile = (
        기본.get("나이", 0) > 0
        or 기본.get("성별", "").strip()
        or 기본.get("거주지역", "").strip()
        or any(고용.get("고용상태", {}).values())
        or profile.get("관심키워드")
    )

    if has_profile:
        return passes_profile_filter(item, profile)
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
    print(f"  수집 대상: 기업마당 · K-스타트업 · 소진공 · 복지로 · 고용24 · 농림부")
    print(f"  마감 임박 기준: {alert_days}일 이내")

    # 프로필 요약 출력
    기본 = profile.get("기본정보", {})
    고용 = profile.get("고용소득", {})
    age    = 기본.get("나이", 0)
    gender = 기본.get("성별", "")
    region = 기본.get("거주지역", "")
    emp    = [k for k, v in 고용.get("고용상태", {}).items() if v]
    active_kws = build_active_keywords(profile)

    if age or gender or region or emp:
        print(f"\n  내 프로필")
        if age:    print(f"    나이:      {age}세")
        if gender: print(f"    성별:      {gender}")
        if region: print(f"    지역:      {region}")
        if emp:    print(f"    고용상태:  {', '.join(emp)}")
        if active_kws:
            print(f"    매칭키워드: {', '.join(active_kws[:10])}{'...' if len(active_kws)>10 else ''}")
    print(f"{'='*55}\n")

    # 수집
    raw = []

    print("  [기업마당] 소상공인·중소기업 수집 중...")
    items = fetch_bizinfo(per_page=100)
    raw.extend([normalize_bizinfo(i) for i in items if i])
    print(f"  → {len(items)}건")

    print("  [K-스타트업] 창업지원사업 수집 중...")
    items = fetch_kstartup(per_page=100)
    raw.extend([normalize_kstartup(i) for i in items if i])
    print(f"  → {len(items)}건")

    print("  [소진공] 소상공인 전용 수집 중...")
    items = fetch_soss(per_page=100)
    raw.extend([normalize_soss(i) for i in items if i])
    print(f"  → {len(items)}건")

    print("  [복지로] 복지·생활 수집 중...")
    items = fetch_welfare(per_page=100)
    raw.extend([normalize_welfare(i) for i in items if i])
    print(f"  → {len(items)}건")

    print("  [고용24] 청년·취업·중장년 수집 중...")
    items = fetch_youth_jobs(per_page=100)
    raw.extend([normalize_youth(i) for i in items if i])
    print(f"  → {len(items)}건")

    print("  [고용24] 추가 취업지원 수집 중...")
    items2 = fetch_youth_jobs_additional(per_page=100)
    raw.extend([normalize_youth(i) for i in items2 if i])
    print(f"  → {len(items2)}건")

    print("  [농림부] 농업·농촌 지원사업 수집 중...")
    items = fetch_agriculture(per_page=100)
    raw.extend([normalize_agriculture(i) for i in items if i])
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
