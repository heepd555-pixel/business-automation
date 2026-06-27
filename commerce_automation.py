# 커머스 업무 자동화 (스마트스토어 + 쿠팡 + 카페24)
import requests
import os
import hmac
import hashlib
from datetime import datetime
from email_sender import send_email
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# 1. 네이버 스마트스토어
# ─────────────────────────────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def get_naver_token():
    url = "https://api.commerce.naver.com/external/v1/oauth2/token"
    payload = {
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "grant_type": "client_credentials",
        "type": "SELF"
    }
    res = requests.post(url, json=payload)
    return res.json()["access_token"]

def get_naver_orders():
    """오늘 신규 주문 가져오기"""
    token = get_naver_token()
    today = datetime.now().strftime("%Y-%m-%dT00:00:00.000Z")
    url = "https://api.commerce.naver.com/external/v1/pay-order/seller/product-orders/query"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "placeOrderBeginDateTime": today,
        "paymentDateType": "PAY_WAITING",
        "limitCount": 50
    }
    res = requests.post(url, headers=headers, json=payload)
    orders = res.json().get("data", {}).get("contents", [])
    print(f"✅ 스마트스토어 신규 주문 {len(orders)}건")
    return orders

def confirm_naver_order(order_id):
    """주문 발주 확인 처리"""
    token = get_naver_token()
    url = f"https://api.commerce.naver.com/external/v1/pay-order/seller/product-orders/{order_id}/claim/dispatch"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.post(url, headers=headers)
    print(f"✅ 스마트스토어 발주확인: {order_id}")
    return res.status_code == 200


# ─────────────────────────────────────────
# 2. 쿠팡
# ─────────────────────────────────────────
COUPANG_ACCESS_KEY = os.getenv("COUPANG_ACCESS_KEY")
COUPANG_SECRET_KEY = os.getenv("COUPANG_SECRET_KEY")
COUPANG_VENDOR_ID = os.getenv("COUPANG_VENDOR_ID")

def coupang_signature(method, path, secret_key):
    """쿠팡 API 서명 생성"""
    datetime_str = datetime.utcnow().strftime("%y%m%dT%H%M%SZ")
    message = datetime_str + method + path
    signature = hmac.new(secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()
    return datetime_str, signature

def get_coupang_orders():
    """쿠팡 신규 주문 가져오기"""
    path = f"/v2/providers/openapi/apis/api/v4/vendors/{COUPANG_VENDOR_ID}/ordersheets"
    method = "GET"
    datetime_str, signature = coupang_signature(method, path, COUPANG_SECRET_KEY)

    headers = {
        "Authorization": f"CEA algorithm=HmacSHA256, access-key={COUPANG_ACCESS_KEY}, signed-date={datetime_str}, signature={signature}",
        "Content-Type": "application/json"
    }
    url = f"https://api-gateway.coupang.com{path}?status=ACCEPT&createdAtFrom={datetime.now().strftime('%Y-%m-%d')}"
    res = requests.get(url, headers=headers)
    orders = res.json().get("data", [])
    print(f"✅ 쿠팡 신규 주문 {len(orders)}건")
    return orders


# ─────────────────────────────────────────
# 3. 카페24
# ─────────────────────────────────────────
CAFE24_MALL_ID = os.getenv("CAFE24_MALL_ID")
CAFE24_ACCESS_TOKEN = os.getenv("CAFE24_ACCESS_TOKEN")

def get_cafe24_orders():
    """카페24 오늘 주문 가져오기"""
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://{CAFE24_MALL_ID}.cafe24api.com/api/v2/orders"
    headers = {
        "Authorization": f"Bearer {CAFE24_ACCESS_TOKEN}",
        "X-Cafe24-Api-Version": "2024-03-01"
    }
    params = {"start_date": today, "end_date": today, "limit": 100}
    res = requests.get(url, headers=headers, params=params)
    orders = res.json().get("orders", [])
    print(f"✅ 카페24 신규 주문 {len(orders)}건")
    return orders


# ─────────────────────────────────────────
# 전체 통합 자동화 실행
# ─────────────────────────────────────────
def run_all():
    print(f"\n🚀 {datetime.now().strftime('%Y-%m-%d %H:%M')} 주문 수집 시작\n")

    naver_orders = get_naver_orders()
    coupang_orders = get_coupang_orders()
    cafe24_orders = get_cafe24_orders()

    total = len(naver_orders) + len(coupang_orders) + len(cafe24_orders)

    # 사장님에게 요약 이메일 발송
    send_email(
        to="owner@example.com",
        subject=f"[주문 요약] 오늘 총 {total}건",
        body=f"""
        <h2>📦 오늘의 주문 현황</h2>
        <table border="1" cellpadding="8">
            <tr><th>플랫폼</th><th>주문 건수</th></tr>
            <tr><td>스마트스토어</td><td>{len(naver_orders)}건</td></tr>
            <tr><td>쿠팡</td><td>{len(coupang_orders)}건</td></tr>
            <tr><td>카페24</td><td>{len(cafe24_orders)}건</td></tr>
            <tr><td><strong>합계</strong></td><td><strong>{total}건</strong></td></tr>
        </table>
        <p>자동 수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        """
    )
    print(f"\n✅ 완료! 총 {total}건 → 사장님 이메일 발송")

if __name__ == "__main__":
    run_all()
