# 이메일 자동 발송 (Python)
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")

def send_email(to, subject, body):
    msg = MIMEMultipart()
    msg["From"] = GMAIL_USER
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, to, msg.as_string())
    print(f"✅ 발송 완료: {to}")

# 사용 예시
send_email(
    to="customer@example.com",
    subject="주문이 확인됐습니다!",
    body="""
    <h2>안녕하세요 고객님!</h2>
    <p>주문이 정상적으로 접수됐습니다.</p>
    <p>배송 시작 시 다시 안내드리겠습니다. 감사합니다 😊</p>
    """
)
# Gmail 앱 비밀번호 발급 방법: Google 계정 → 보안 → 2단계 인증 켜기 → 앱 비밀번호 생성