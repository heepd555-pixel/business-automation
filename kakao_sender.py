# 카카오 알림톡 (Python)
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("KAKAO_API_KEY")
SENDER_KEY = os.getenv("KAKAO_SENDER_KEY")
TEMPLATE_CODE = os.getenv("KAKAO_TEMPLATE_CODE")

def send_kakao(phone, customer_name, order_number):
    url = "https://api-alimtalk.cloud.toast.com/alimtalk/v2.3/appkeys/{API_KEY}/messages"

    payload = {
        "senderKey": SENDER_KEY,
        "templateCode": TEMPLATE_CODE,
        "recipientList": [
            {
                "recipientNo": phone,  # 수신자 번호 (예: 01012345678)
                "templateParameter": {
                    "customer_name": customer_name,
                    "order_number": order_number
                }
            }
        ]
    }

    headers = {"Content-Type": "application/json;charset=UTF-8"}
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 200:
        print(f"✅ 카카오 발송 완료: {phone}")
    else:
        print(f"❌ 발송 실패: {response.text}")

# 사용 예시
send_kakao(
    phone="01012345678",
    customer_name="홍길동",
    order_number="ORD-20260627-001"
)


# 카카오 알림톡 발급 순서: 카카오 비즈니스 채널 개설 → 알림톡 신청 → 템플릿 심사 승인 (약 2~3일 소요)