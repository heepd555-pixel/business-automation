import os
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", GMAIL_USER)  # 오류 알림 받을 이메일 (기본: 본인)

def send_error_alert(job_name: str, error: Exception):
    """오류 발생 시 이메일 알림 발송"""
    try:
        msg = MIMEMultipart()
        msg["From"] = GMAIL_USER
        msg["To"] = ALERT_EMAIL
        msg["Subject"] = f"[자동화 오류] {job_name} 실패 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        body = f"""
        <h3>자동화 스크립트 오류 발생</h3>
        <p><b>작업명:</b> {job_name}</p>
        <p><b>시각:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><b>오류 내용:</b></p>
        <pre>{traceback.format_exc()}</pre>
        <p>스크립트를 확인해 주세요.</p>
        """
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, ALERT_EMAIL, msg.as_string())
        print(f"[오류 알림 발송 완료] {ALERT_EMAIL}")
    except Exception:
        print(f"[오류 알림 발송 실패] 이메일 설정 확인 필요")

def is_allowed_time(start_hour: int = 8, end_hour: int = 21) -> bool:
    """광고성 메시지 발송 허용 시간 확인 (기본: 오전 8시 ~ 오후 9시)"""
    hour = datetime.now().hour
    return start_hour <= hour < end_hour

def safe_run(job_name: str, func, *args, **kwargs):
    """오류 안전 실행 래퍼 — 오류 발생 시 알림 발송 후 계속 실행"""
    try:
        func(*args, **kwargs)
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] ❌ {job_name} 오류: {e}")
        send_error_alert(job_name, e)
