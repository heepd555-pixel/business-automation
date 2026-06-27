# 콘텐츠 스케줄러 (Google Sheets 기반)
# 시트에 콘텐츠 목록 작성 → 날짜/시간에 맞춰 자동 발행
import gspread
import os
import schedule
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from sns_multi_post import post_to_all

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(os.getenv("GOOGLE_CREDENTIALS_FILE"), scopes=SCOPES)
client = gspread.authorize(creds)
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")

# 시트 컬럼 구조:
# 날짜 | 시간 | 내용 | 이미지URL | 플랫폼 | 발행여부

def get_scheduled_content():
    """오늘 발행할 콘텐츠 목록 가져오기"""
    sheet = client.open_by_key(SHEET_ID).worksheet("콘텐츠스케줄")
    rows = sheet.get_all_records()
    today = datetime.now().strftime("%Y-%m-%d")

    scheduled = [
        row for row in rows
        if row["날짜"] == today and row["발행여부"] != "완료"
    ]
    print(f"✅ 오늘 발행 예정 콘텐츠: {len(scheduled)}개")
    return scheduled, sheet

def mark_as_done(sheet, row_index):
    """발행 완료 표시"""
    sheet.update_cell(row_index + 2, 6, "완료")  # 6번째 컬럼 = 발행여부

def check_and_publish():
    """지금 시간에 발행해야 할 콘텐츠 확인 후 발행"""
    now = datetime.now().strftime("%H:%M")
    scheduled_list, sheet = get_scheduled_content()

    for i, content in enumerate(scheduled_list):
        if content["시간"] == now:
            platforms = content["플랫폼"].split(",")  # 예: "twitter,instagram"
            platforms = [p.strip() for p in platforms]

            print(f"\n⏰ {now} 발행 시작: {content['내용'][:30]}...")
            post_to_all(
                text=content["내용"],
                image_url=content.get("이미지URL") or None,
                platforms=platforms
            )
            mark_as_done(sheet, i)

def add_content_to_schedule(date, time_str, text, image_url="", platforms="twitter"):
    """시트에 새 콘텐츠 추가"""
    sheet = client.open_by_key(SHEET_ID).worksheet("콘텐츠스케줄")
    sheet.append_row([date, time_str, text, image_url, platforms, ""])
    print(f"✅ 스케줄 추가 완료: {date} {time_str} - {text[:30]}...")

def run_scheduler():
    """1분마다 스케줄 확인"""
    print("🕐 콘텐츠 스케줄러 시작 (Ctrl+C로 종료)")
    schedule.every(1).minutes.do(check_and_publish)
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    # 콘텐츠 추가 예시
    add_content_to_schedule(
        date=datetime.now().strftime("%Y-%m-%d"),
        time_str="09:00",
        text="오늘의 아침 인사 🌅 좋은 하루 되세요! #일상 #크리에이터",
        platforms="twitter,slack"
    )

    # 스케줄러 실행
    # run_scheduler()
