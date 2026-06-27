# Google Sheets 자동 대시보드
import gspread
import os
from google.oauth2.service_account import Credentials
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(os.getenv("GOOGLE_CREDENTIALS_FILE"), scopes=SCOPES)
client = gspread.authorize(creds)

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
workbook = client.open_by_key(SHEET_ID)

# 주문 데이터 시트 (컬럼: 날짜 | 고객명 | 상품 | 수량 | 금액 | 상태)
orders_sheet = workbook.worksheet("주문내역")

def get_orders():
    return orders_sheet.get_all_records()

def build_dashboard():
    orders = get_orders()
    today = datetime.today().strftime("%Y-%m-%d")

    total_sales = 0
    today_sales = 0
    today_orders = 0
    product_counter = defaultdict(int)
    status_counter = defaultdict(int)

    for row in orders:
        amount = int(str(row["금액"]).replace(",", ""))
        total_sales += amount
        product_counter[row["상품"]] += int(row["수량"])
        status_counter[row["상태"]] += 1

        if row["날짜"] == today:
            today_sales += amount
            today_orders += 1

    # 베스트 상품 Top 3
    top_products = sorted(product_counter.items(), key=lambda x: x[1], reverse=True)[:3]

    # 대시보드 시트에 결과 기록
    try:
        dash = workbook.worksheet("대시보드")
    except gspread.WorksheetNotFound:
        dash = workbook.add_worksheet(title="대시보드", rows=30, cols=5)

    dash.clear()
    dash.update("A1", [
        ["📊 매출 대시보드", f"업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        [""],
        ["항목", "값"],
        ["전체 누적 매출", f"{total_sales:,}원"],
        ["오늘 매출", f"{today_sales:,}원"],
        ["오늘 주문 건수", f"{today_orders}건"],
        [""],
        ["📦 베스트 상품 Top 3", ""],
    ])

    for i, (product, qty) in enumerate(top_products, start=9):
        dash.update_cell(i, 1, f"{i-8}위. {product}")
        dash.update_cell(i, 2, f"{qty}개")

    dash.update(f"A{12}", [
        [""],
        ["📋 주문 상태 현황", ""],
    ])
    for i, (status, count) in enumerate(status_counter.items(), start=14):
        dash.update_cell(i, 1, status)
        dash.update_cell(i, 2, f"{count}건")

    print("✅ 대시보드 업데이트 완료!")

if __name__ == "__main__":
    build_dashboard()
