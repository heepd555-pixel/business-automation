# Google Sheets + 이메일 자동 발송
import gspread
import os
from google.oauth2.service_account import Credentials
from email_sender import send_email
from dotenv import load_dotenv

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file(os.getenv("GOOGLE_CREDENTIALS_FILE"), scopes=SCOPES)
client = gspread.authorize(creds)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
sheet = client.open_by_key(SHEET_ID).sheet1

def send_to_all_customers():
    rows = sheet.get_all_records()
    # 시트 컬럼 예시: 이름 | 이메일 | 주문번호 | 발송여부

    for row in rows:
        if row["발송여부"] == "완료":
            continue  # 이미 보낸 고객 건너뜀

        send_email(
            to=row["이메일"],
            subject=f"[주문확인] {row['주문번호']}",
            body=f"""
            <h2>{row['이름']}님, 주문 감사합니다!</h2>
            <p>주문번호: <strong>{row['주문번호']}</strong></p>
            <p>배송 시작 시 다시 안내드리겠습니다.</p>
            """
        )

        # 발송 완료 표시
        cell = sheet.find(row["이메일"])
        sheet.update_cell(cell.row, 4, "완료")
        print(f"✅ {row['이름']} ({row['이메일']}) 발송 완료")

if __name__ == "__main__":
    send_to_all_customers()


#필요한 패키지 설치:
# pip install gspread google-auth 