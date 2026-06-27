# 인스타그램 게시물 예약 발행 (Meta Graph API)
# 발급: developers.facebook.com → 앱 생성 → Instagram Graph API
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
IG_USER_ID = os.getenv("IG_USER_ID")
IG_ACCESS_TOKEN = os.getenv("IG_ACCESS_TOKEN")

BASE_URL = "https://graph.facebook.com/v19.0"

def upload_image(image_url, caption):
    """이미지 컨테이너 생성 (발행 전 단계)"""
    url = f"{BASE_URL}/{IG_USER_ID}/media"
    params = {
        "image_url": image_url,  # 공개 접근 가능한 이미지 URL
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }
    res = requests.post(url, params=params).json()
    container_id = res.get("id")
    print(f"✅ 이미지 컨테이너 생성: {container_id}")
    return container_id

def publish_post(container_id):
    """컨테이너를 실제 게시물로 발행"""
    url = f"{BASE_URL}/{IG_USER_ID}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": IG_ACCESS_TOKEN
    }
    res = requests.post(url, params=params).json()
    post_id = res.get("id")
    print(f"✅ 인스타그램 발행 완료: {post_id}")
    return post_id

def get_account_info():
    """계정 기본 정보 조회"""
    url = f"{BASE_URL}/{IG_USER_ID}"
    params = {
        "fields": "username,followers_count,media_count",
        "access_token": IG_ACCESS_TOKEN
    }
    res = requests.get(url, params=params).json()
    print(f"\n📊 인스타그램 계정 정보")
    print(f"  아이디: @{res.get('username')}")
    print(f"  팔로워: {res.get('followers_count', 0):,}명")
    print(f"  게시물 수: {res.get('media_count', 0)}개")
    return res

def get_recent_posts():
    """최근 게시물 성과 조회"""
    url = f"{BASE_URL}/{IG_USER_ID}/media"
    params = {
        "fields": "id,caption,like_count,comments_count,timestamp",
        "limit": 10,
        "access_token": IG_ACCESS_TOKEN
    }
    res = requests.get(url, params=params).json()
    posts = res.get("data", [])

    print(f"\n📋 최근 게시물 성과 (최근 {len(posts)}개)")
    for i, post in enumerate(posts, 1):
        caption = (post.get("caption", "")[:30] + "...") if post.get("caption") else "캡션 없음"
        print(f"  {i}. {caption}")
        print(f"     ❤️ 좋아요: {post.get('like_count', 0)} | 💬 댓글: {post.get('comments_count', 0)}")
    return posts

if __name__ == "__main__":
    get_account_info()
    get_recent_posts()

    # 게시물 발행 예시
    # container_id = upload_image(
    #     image_url="https://example.com/image.jpg",
    #     caption="오늘의 콘텐츠 🔥 #자동화 #크리에이터"
    # )
    # publish_post(container_id)
