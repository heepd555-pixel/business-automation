import schedule
import time
from datetime import datetime

from commerce_automation import run_all as commerce
from work_tool_integration import morning_briefing
from external_data_collector import run_all as data_collect
from competitor_crawler import run as competitor
from youtube_analytics import send_weekly_report
from content_scheduler import check_and_publish
from error_handler import safe_run, is_allowed_time

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}")

# ─────────────────────────────────────────
# 광고성 메시지 시간 제한 적용 작업
# 정보통신망법: 오후 9시 ~ 오전 8시 광고성 발송 금지
# ─────────────────────────────────────────

def guarded_commerce():
    if not is_allowed_time():
        log("⛔ 야간 시간대 — 커머스 알림 발송 건너뜀 (오전 8시 이후 재시작)")
        return
    safe_run("커머스 주문 수집", commerce)

def guarded_morning():
    safe_run("모닝 브리핑", morning_briefing)

def guarded_data():
    safe_run("외부 데이터 수집", data_collect)

def guarded_content():
    if not is_allowed_time():
        return  # 야간엔 조용히 건너뜀
    safe_run("콘텐츠 예약 발행", check_and_publish)

def guarded_youtube():
    safe_run("유튜브 주간 리포트", send_weekly_report)

def guarded_competitor():
    safe_run("경쟁사 가격 수집", competitor, "내 상품 키워드")

# ─────────────────────────────────────────
# 스케줄 등록
# ─────────────────────────────────────────

schedule.every().day.at("08:00").do(guarded_morning)
schedule.every().day.at("09:00").do(guarded_commerce)
schedule.every().day.at("09:10").do(guarded_data)
schedule.every(1).minutes.do(guarded_content)
schedule.every().monday.at("09:00").do(guarded_youtube)
schedule.every().monday.at("09:30").do(guarded_competitor)

# ─────────────────────────────────────────
# 실행
# ─────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  자동화 스케줄러 시작")
    print("  종료하려면 Ctrl+C 를 누르세요")
    print("=" * 50)
    print()
    print("📅 등록된 스케줄:")
    print("  08:00 매일  → 모닝 브리핑 (Slack + Notion)")
    print("  09:00 매일  → 커머스 주문 수집 + 이메일 발송")
    print("  09:10 매일  → 날씨/환율/뉴스 수집")
    print("  매 1분      → 콘텐츠 예약 발행 확인")
    print("  월 09:00   → 유튜브 주간 리포트")
    print("  월 09:30   → 경쟁사 가격 수집")
    print()
    print("⚠  오류 발생 시 이메일로 자동 알림 발송")
    print("⚠  오후 9시 ~ 오전 8시 광고성 발송 자동 차단")
    print()

    while True:
        schedule.run_pending()
        time.sleep(30)
