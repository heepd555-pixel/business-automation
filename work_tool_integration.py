# 업무 도구 연동 자동화 (Slack + Notion + Google Calendar)
import requests
import os
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

def send_slack(message, channel="#업무알림"):
    payload = {
        "channel": channel,
        "text": message,
        "username": "자동화봇",
        "icon_emoji": ":robot_face:"
    }
    res = requests.post(SLACK_WEBHOOK_URL, json=payload)
    print(f"✅ Slack 발송 완료: {channel}")
    return res.status_code == 200

def send_slack_block(title, items):
    """표 형태로 슬랙 메시지 발송"""
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": title}},
        {"type": "divider"},
    ]
    for item in items:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"• {item}"}
        })
    payload = {"channel": "#업무알림", "blocks": blocks}
    requests.post(SLACK_WEBHOOK_URL, json=payload)
    print(f"✅ Slack 블록 메시지 발송 완료")


# ─────────────────────────────────────────
# 2. Notion 자동 기록
# 발급: https://www.notion.so/my-integrations
# ─────────────────────────────────────────
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def add_notion_record(title, content, category="업무일지"):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": {
            "제목": {"title": [{"text": {"content": title}}]},
            "카테고리": {"select": {"name": category}},
            "날짜": {"date": {"start": datetime.now().strftime("%Y-%m-%d")}}
        },
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": content}}]
                }
            }
        ]
    }
    res = requests.post(url, headers=headers, json=payload)
    print(f"✅ Notion 기록 완료: {title}")
    return res.status_code == 200


# ─────────────────────────────────────────
# 3. Google Calendar 일정 추가
# 발급: Google Cloud Console → Calendar API 활성화
# ─────────────────────────────────────────
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_calendar_service():
    creds = Credentials.from_service_account_file(os.getenv("GOOGLE_CREDENTIALS_FILE"), scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)

def add_calendar_event(title, description, start_datetime, duration_hours=1):
    service = get_calendar_service()
    end_datetime = start_datetime + timedelta(hours=duration_hours)
    event = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_datetime.isoformat(), "timeZone": "Asia/Seoul"},
        "end": {"dateTime": end_datetime.isoformat(), "timeZone": "Asia/Seoul"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 30}]
        }
    }
    result = service.events().insert(calendarId="primary", body=event).execute()
    print(f"✅ 캘린더 일정 추가: {title}")
    return result.get("htmlLink")

def get_todays_events():
    """오늘 일정 가져오기"""
    service = get_calendar_service()
    today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat() + "+09:00"
    today_end = datetime.now().replace(hour=23, minute=59, second=59).isoformat() + "+09:00"
    events = service.events().list(
        calendarId="primary",
        timeMin=today_start,
        timeMax=today_end,
        singleEvents=True,
        orderBy="startTime"
    ).execute()
    return events.get("items", [])


# ─────────────────────────────────────────
# 통합 실행: 오늘 일정 → Slack 알림 + Notion 기록
# ─────────────────────────────────────────
def morning_briefing():
    print(f"\n🌅 {datetime.now().strftime('%Y-%m-%d')} 모닝 브리핑 시작\n")

    events = get_todays_events()
    event_list = [
        f"{e['start'].get('dateTime', e['start'].get('date'))[:16]} - {e['summary']}"
        for e in events
    ] or ["오늘 일정 없음"]

    # Slack으로 오늘 일정 공유
    send_slack_block(
        title=f"📅 {datetime.now().strftime('%Y년 %m월 %d일')} 오늘의 일정",
        items=event_list
    )

    # Notion에 업무일지 자동 생성
    add_notion_record(
        title=f"{datetime.now().strftime('%Y-%m-%d')} 업무일지",
        content="\n".join(event_list),
        category="업무일지"
    )

    print("\n✅ 모닝 브리핑 완료!")

if __name__ == "__main__":
    morning_briefing()
