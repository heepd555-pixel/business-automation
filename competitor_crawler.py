# 경쟁사 가격/리뷰 수집 (네이버 쇼핑 API + 쿠팡 파트너스 API)
import requests
import os
import hmac
import hashlib
import csv
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# 1. 네이버 쇼핑 (검색 API)
# 발급: https://developers.naver.com → 쇼핑 검색 API
# ─────────────────────────────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def search_naver_shopping(keyword, display=10):
    """네이버 쇼핑 상품 가격 수집"""
    url = "https://openapi.naver.com/v1/search/shop.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": keyword, "display": display, "sort": "sim"}
    res = requests.get(url, headers=headers, params=params).json()

    results = []
    for item in res.get("items", []):
        results.append({
            "플랫폼": "네이버쇼핑",
            "상품명": item["title"].replace("<b>", "").replace("</b>", ""),
            "가격": f"{int(item['lprice']):,}원",
            "브랜드": item.get("brand", "-"),
            "카테고리": item.get("category1", "-"),
            "링크": item["link"]
        })

    print(f"✅ 네이버 쇼핑 '{keyword}' 검색 결과 {len(results)}개")
    return results


# ─────────────────────────────────────────
# 2. 쿠팡 파트너스 API (공식)
# 발급: https://partners.coupang.com → API 키 발급
# ─────────────────────────────────────────
COUPANG_ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY")
COUPANG_SECRET_KEY = os.getenv("COUPANG_SECRET_KEY")

def coupang_auth_header(method, path):
    """쿠팡 API 인증 헤더 생성"""
    datetime_str = datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + path
    signature = hmac.new(
        COUPANG_SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return {
        "Authorization": f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, signed-date={datetime_str}, signature={signature}",
        "Content-Type": "application/json"
    }

def search_coupang(keyword, limit=10):
    """쿠팡 파트너스 API로 상품 검색"""
    path = f"/v2/providers/affiliate_open_api/apis/openapi/products/search?keyword={keyword}&limit={limit}"
    headers = coupang_auth_header("GET", path)
    url = f"https://api-gateway.coupang.com{path}"
    res = requests.get(url, headers=headers).json()

    results = []
    for item in res.get("data", {}).get("productData", []):
        results.append({
            "플랫폼": "쿠팡",
            "상품명": item.get("productName", "-"),
            "가격": f"{item.get('salePriceL', 0):,}원",
            "별점": item.get("ratingDetails", {}).get("rating", "-"),
            "리뷰수": f"{item.get('ratingDetails', {}).get('ratingCount', 0):,}개",
            "링크": item.get("productUrl", "-")
        })

    print(f"✅ 쿠팡 '{keyword}' API 결과 {len(results)}개")
    return results


# ─────────────────────────────────────────
# 3. 결과 저장 (CSV)
# ─────────────────────────────────────────
def save_to_csv(data, keyword):
    filename = f"competitor_{keyword}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    if not data:
        print("❌ 저장할 데이터 없음")
        return

    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"✅ CSV 저장 완료: {filename}")
    return filename


# ─────────────────────────────────────────
# 4. 가격 분석 요약
# ─────────────────────────────────────────
def analyze_prices(data):
    prices = []
    for item in data:
        try:
            price = int(item["가격"].replace(",", "").replace("원", ""))
            prices.append(price)
        except Exception:
            continue

    if not prices:
        print("❌ 가격 분석 불가")
        return

    print(f"\n📊 가격 분석 결과")
    print(f"  최저가: {min(prices):,}원")
    print(f"  최고가: {max(prices):,}원")
    print(f"  평균가: {sum(prices) // len(prices):,}원")
    print(f"  수집 상품수: {len(prices)}개")


# ─────────────────────────────────────────
# 통합 실행
# ─────────────────────────────────────────
def run(keyword):
    print(f"\n🔍 '{keyword}' 경쟁사 데이터 수집 시작\n")

    naver_data = search_naver_shopping(keyword)
    coupang_data = search_coupang(keyword)

    all_data = naver_data + coupang_data
    save_to_csv(all_data, keyword)
    analyze_prices(all_data)

    print(f"\n✅ 완료! 총 {len(all_data)}개 상품 수집")

if __name__ == "__main__":
    run("무선이어폰")  # 원하는 키워드로 변경
