# 외부 데이터 수집 자동화 (날씨 + 환율 + 뉴스)
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY")

def get_weather(city="Seoul"):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "kr"}
    res = requests.get(url, params=params).json()
    return {
        "도시": city,
        "날씨": res["weather"][0]["description"],
        "기온": f"{res['main']['temp']}°C",
        "습도": f"{res['main']['humidity']}%",
        "풍속": f"{res['wind']['speed']}m/s"
    }


# ─────────────────────────────────────────
# 2. 환율 (ExchangeRate API)
# 발급: https://exchangerate-api.com (무료 플랜 가능)
# ─────────────────────────────────────────
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")

def get_exchange_rates():
    url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_API_KEY}/latest/USD"
    res = requests.get(url).json()
    rates = res["conversion_rates"]
    return {
        "USD → KRW": f"{rates['KRW']:,.0f}원",
        "USD → JPY": f"{rates['JPY']:,.0f}엔",
        "USD → EUR": f"{rates['EUR']:.4f}유로",
        "기준시각": res["time_last_update_utc"]
    }


# ─────────────────────────────────────────
# 3. 뉴스 (Naver News API)
# 발급: https://developers.naver.com
# ─────────────────────────────────────────
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

def get_news(keyword="중소기업", display=5):
    url = "https://openapi.naver.com/v1/search/news.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": keyword, "display": display, "sort": "date"}
    res = requests.get(url, headers=headers, params=params).json()
    return [
        {
            "제목": item["title"].replace("<b>", "").replace("</b>", ""),
            "링크": item["link"],
            "날짜": item["pubDate"]
        }
        for item in res.get("items", [])
    ]


# ─────────────────────────────────────────
# 통합 실행 + 출력
# ─────────────────────────────────────────
def run_all():
    print(f"\n📡 {datetime.now().strftime('%Y-%m-%d %H:%M')} 외부 데이터 수집\n")

    print("🌤 날씨")
    weather = get_weather("Seoul")
    for k, v in weather.items():
        print(f"  {k}: {v}")

    print("\n💱 환율 (USD 기준)")
    rates = get_exchange_rates()
    for k, v in rates.items():
        print(f"  {k}: {v}")

    print("\n📰 최신 뉴스 (중소기업)")
    news = get_news("중소기업")
    for i, item in enumerate(news, 1):
        print(f"  {i}. {item['제목']}")
        print(f"     {item['링크']}")

if __name__ == "__main__":
    run_all()
