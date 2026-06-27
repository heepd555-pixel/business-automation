# 전체 자동화 스케줄러
# 이 파일을 실행하면 매일 정해진 시간에 자동으로 실행됩니다
import schedule
import time
from datetime import datetime

from commerce_automation import run_all as commerce
from work_tool_integration import morning_briefing
from external_data_collector import run_all as data_collect
from competitor_crawler import run as competitor
from youtube_analytics import send_weekly_report
from content_scheduler import check_and_publish

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}")

# ─────────────────────────────────────────
# 스케줄 등록
# ─────────────────────────────────────────

# 매일 실행
schedule.every().day.at("08:00").do(lambda: log("모닝 브리핑 시작") or morning_briefing())
schedule.every().day.at("09:00").do(lambda: log("주문 수집 시작") or commerce())
schedule.every().day.at("09:10").do(lambda: log("외부 데이터 수집 시작") or data_collect())

# 1분마다 콘텐츠 스케줄 확인 (예약 발행)
schedule.every(1).minutes.do(check_and_publish)

# 매주 월요일 오전 9시 — 유튜브 주간 리포트
schedule.every().monday.at("09:00").do(lambda: log("유튜브 주간 리포트 발송") or send_weekly_report())

# 매주 월요일 오전 9시 30분 — 경쟁사 가격 수집
schedule.every().monday.at("09:30").do(lambda: log("경쟁사 가격 수집 시작") or competitor("내 상품 키워드"))

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

    while True:
        schedule.run_pending()
        time.sleep(30)
