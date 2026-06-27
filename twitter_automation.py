# 트위터/X 자동 포스팅 (Twitter API v2)
# 발급: developer.twitter.com → 프로젝트 생성 → API 키 발급
import requests
import os
from requests_oauthlib import OAuth1
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("TWITTER_API_KEY")
API_SECRET = os.getenv("TWITTER_API_SECRET")
ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

BASE_URL = "https://api.twitter.com/2"

def get_auth():
    return OAuth1(API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)

def post_tweet(text):
    """트윗 작성"""
    url = f"{BASE_URL}/tweets"
    payload = {"text": text}
    res = requests.post(url, json=payload, auth=get_auth()).json()
    tweet_id = res.get("data", {}).get("id")
    print(f"✅ 트윗 발행 완료: {tweet_id}")
    print(f"   내용: {text[:50]}...")
    return tweet_id

def delete_tweet(tweet_id):
    """트윗 삭제"""
    url = f"{BASE_URL}/tweets/{tweet_id}"
    res = requests.delete(url, auth=get_auth())
    print(f"✅ 트윗 삭제 완료: {tweet_id}")
    return res.status_code == 200

def get_my_timeline(max_results=10):
    """내 최근 트윗 조회"""
    url = f"{BASE_URL}/users/me"
    res = requests.get(url, auth=get_auth()).json()
    user_id = res.get("data", {}).get("id")

    url = f"{BASE_URL}/users/{user_id}/tweets"
    params = {
        "max_results": max_results,
        "tweet.fields": "public_metrics,created_at"
    }
    res = requests.get(url, params=params, auth=get_auth()).json()
    tweets = res.get("data", [])

    print(f"\n📋 최근 트윗 성과 ({len(tweets)}개)")
    for i, tweet in enumerate(tweets, 1):
        metrics = tweet.get("public_metrics", {})
        text = tweet.get("text", "")[:40]
        print(f"  {i}. {text}...")
        print(f"     ❤️ {metrics.get('like_count', 0)} | 🔁 {metrics.get('retweet_count', 0)} | 💬 {metrics.get('reply_count', 0)}")
    return tweets

def post_thread(tweets_list):
    """쓰레드 작성 (연속 트윗)"""
    reply_to_id = None
    for i, text in enumerate(tweets_list):
        url = f"{BASE_URL}/tweets"
        payload = {"text": text}
        if reply_to_id:
            payload["reply"] = {"in_reply_to_tweet_id": reply_to_id}

        res = requests.post(url, json=payload, auth=get_auth()).json()
        reply_to_id = res.get("data", {}).get("id")
        print(f"✅ 쓰레드 {i+1}/{len(tweets_list)} 발행: {text[:30]}...")
    print("✅ 쓰레드 발행 완료!")

if __name__ == "__main__":
    get_my_timeline()

    # 단일 트윗 예시
    # post_tweet("오늘의 인사이트 💡 자동화로 시간을 아끼세요! #생산성 #자동화")

    # 쓰레드 예시
    # post_thread([
    #     "1/ 오늘 배운 것 🧵",
    #     "2/ 첫 번째 내용입니다.",
    #     "3/ 두 번째 내용입니다.",
    #     "4/ 마무리입니다. 팔로우 부탁드려요!"
    # ])
