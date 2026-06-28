import requests
import hashlib
import hmac
import time
import random
import string
import os
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
SOLAPI_API_KEY    = os.getenv("SOLAPI_API_KEY")
SOLAPI_API_SECRET = os.getenv("SOLAPI_API_SECRET")
SOLAPI_FROM       = os.getenv("SOLAPI_SENDER_NUMBER")  # 발신번호 (예: 0212345678)
SOLAPI_PF_ID      = os.getenv("SOLAPI_PF_ID")          # 카카오 채널 ID
SOLAPI_TEMPLATE_ID = os.getenv("SOLAPI_TEMPLATE_ID")   # 알림톡 템플릿 ID

def _auth_header() -> str:
    """솔라피 HMAC-SHA256 인증 헤더 생성"""
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    salt = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    signature = hmac.new(
        SOLAPI_API_SECRET.encode(),
        (date + salt).encode(),
        hashlib.sha256
    ).hexdigest()
    return f"HMAC-SHA256 apiKey={SOLAPI_API_KEY}, date={date}, salt={salt}, signature={signature}"

def send_kakao(phone: str, variables: dict) -> bool:
    """
    카카오 알림톡 발송 (솔라피 경유)

    phone     : 수신자 번호 (예: '01012345678')
    variables : 템플릿 변수 (예: {'#{고객명}': '홍길동', '#{주문번호}': 'ORD-001'})
    """
    url = "https://api.solapi.com/messages/v4/send"
    payload = {
        "message": {
            "to": phone,
            "from": SOLAPI_FROM,
            "kakaoOptions": {
                "pfId": SOLAPI_PF_ID,
                "templateId": SOLAPI_TEMPLATE_ID,
                "variables": variables
            }
        }
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": _auth_header()
    }
    res = requests.post(url, json=payload, headers=headers)
    if res.status_code == 200:
        print(f"✅ 알림톡 발송 완료: {phone}")
        return True
    else:
        print(f"❌ 발송 실패 ({phone}): {res.text}")
        return False

def send_order_confirm(phone: str, customer_name: str, order_number: str) -> bool:
    """주문 확인 알림톡 발송"""
    return send_kakao(phone, {
        "#{고객명}": customer_name,
        "#{주문번호}": order_number
    })

def send_shipping_alert(phone: str, customer_name: str, tracking_number: str) -> bool:
    """배송 시작 알림톡 발송"""
    return send_kakao(phone, {
        "#{고객명}": customer_name,
        "#{운송장번호}": tracking_number
    })

# 사용 예시
if __name__ == "__main__":
    send_order_confirm(
        phone="01012345678",
        customer_name="홍길동",
        order_number="ORD-20260628-001"
    )

# 솔라피 준비 순서:
# 1. solapi.com 회원가입
# 2. 카카오 채널 연동 → pfId 확인
# 3. 알림톡 템플릿 등록 → 심사 승인 (1~2일)
# 4. API Key / API Secret 발급
# 5. .env 파일에 입력
