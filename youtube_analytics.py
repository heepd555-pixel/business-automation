# 유튜브 채널 분석 자동화 (YouTube Data API v3)
# 발급: console.cloud.google.com → YouTube Data API v3 활성화
import os
import csv
from datetime import datetime
from googleapiclient.discovery import build
from dotenv import load_dotenv
from email_sender import send_email

load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
MY_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# ─────────────────────────────────────────
# 내 채널 분석
# ─────────────────────────────────────────
def get_channel_stats(channel_id=None):
    """채널 기본 통계 조회"""
    cid = channel_id or MY_CHANNEL_ID
    res = youtube.channels().list(
        part="snippet,statistics",
        id=cid
    ).execute()

    channel = res["items"][0]
    stats = channel["statistics"]
    info = {
        "채널명": channel["snippet"]["title"],
        "구독자": f"{int(stats.get('subscriberCount', 0)):,}명",
        "총 조회수": f"{int(stats.get('viewCount', 0)):,}회",
        "영상 수": f"{stats.get('videoCount', 0)}개"
    }
    print(f"\n📺 채널 정보: {info['채널명']}")
    for k, v in info.items():
        if k != "채널명":
            print(f"  {k}: {v}")
    return info

def get_recent_videos(max_results=10):
    """최근 업로드 영상 성과 조회"""
    # 최근 영상 ID 목록
    res = youtube.search().list(
        part="id",
        channelId=MY_CHANNEL_ID,
        order="date",
        maxResults=max_results,
        type="video"
    ).execute()

    video_ids = [item["id"]["videoId"] for item in res.get("items", [])]

    # 영상별 상세 통계
    res = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(video_ids)
    ).execute()

    videos = []
    print(f"\n📋 최근 영상 성과 ({len(res['items'])}개)")
    for i, item in enumerate(res["items"], 1):
        stats = item["statistics"]
        title = item["snippet"]["title"]
        published = item["snippet"]["publishedAt"][:10]
        data = {
            "제목": title,
            "업로드일": published,
            "조회수": int(stats.get("viewCount", 0)),
            "좋아요": int(stats.get("likeCount", 0)),
            "댓글": int(stats.get("commentCount", 0))
        }
        videos.append(data)
        print(f"  {i}. {title[:35]}...")
        print(f"     👁 {data['조회수']:,} | 👍 {data['좋아요']:,} | 💬 {data['댓글']:,} ({published})")

    return videos


# ─────────────────────────────────────────
# 경쟁 채널 분석
# ─────────────────────────────────────────
def search_competitor_channels(keyword, max_results=5):
    """키워드로 경쟁 채널 검색 및 비교"""
    res = youtube.search().list(
        part="snippet",
        q=keyword,
        type="channel",
        maxResults=max_results,
        order="viewCount"
    ).execute()

    channel_ids = [item["snippet"]["channelId"] for item in res.get("items", [])]

    res = youtube.channels().list(
        part="snippet,statistics",
        id=",".join(channel_ids)
    ).execute()

    print(f"\n🔍 '{keyword}' 관련 채널 비교")
    competitors = []
    for i, item in enumerate(res["items"], 1):
        stats = item["statistics"]
        data = {
            "채널명": item["snippet"]["title"],
            "구독자": int(stats.get("subscriberCount", 0)),
            "총 조회수": int(stats.get("viewCount", 0)),
            "영상 수": int(stats.get("videoCount", 0))
        }
        competitors.append(data)
        print(f"  {i}. {data['채널명']}")
        print(f"     구독자: {data['구독자']:,}명 | 조회수: {data['총 조회수']:,}회")

    return competitors


# ─────────────────────────────────────────
# 주간 리포트 생성 + 이메일 발송
# ─────────────────────────────────────────
def send_weekly_report():
    """주간 채널 성과 리포트 이메일 발송"""
    channel = get_channel_stats()
    videos = get_recent_videos(5)

    top_video = max(videos, key=lambda x: x["조회수"]) if videos else {}
    total_views = sum(v["조회수"] for v in videos)
    total_likes = sum(v["좋아요"] for v in videos)

    video_rows = "".join([
        f"<tr><td>{v['제목'][:30]}...</td><td>{v['조회수']:,}</td><td>{v['좋아요']:,}</td><td>{v['업로드일']}</td></tr>"
        for v in videos
    ])

    send_email(
        to=os.getenv("GMAIL_USER"),
        subject=f"[유튜브 주간 리포트] {datetime.now().strftime('%Y년 %m월 %d일')}",
        body=f"""
        <h2>📺 {channel['채널명']} 주간 리포트</h2>
        <h3>채널 현황</h3>
        <table border="1" cellpadding="8">
            <tr><th>구독자</th><th>총 조회수</th><th>영상 수</th></tr>
            <tr><td>{channel['구독자']}</td><td>{channel['총 조회수']}</td><td>{channel['영상 수']}</td></tr>
        </table>
        <h3>최근 5개 영상 성과</h3>
        <table border="1" cellpadding="8">
            <tr><th>제목</th><th>조회수</th><th>좋아요</th><th>업로드일</th></tr>
            {video_rows}
        </table>
        <h3>이번 주 요약</h3>
        <p>총 조회수: <strong>{total_views:,}회</strong></p>
        <p>총 좋아요: <strong>{total_likes:,}개</strong></p>
        <p>🏆 베스트 영상: <strong>{top_video.get('제목', '-')[:40]}</strong> ({top_video.get('조회수', 0):,}회)</p>
        """
    )
    print("✅ 주간 리포트 이메일 발송 완료!")

def save_to_csv(videos, filename=None):
    """영상 데이터 CSV 저장"""
    if not filename:
        filename = f"youtube_report_{datetime.now().strftime('%Y%m%d')}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=videos[0].keys())
        writer.writeheader()
        writer.writerows(videos)
    print(f"✅ CSV 저장: {filename}")

if __name__ == "__main__":
    get_channel_stats()
    videos = get_recent_videos()
    save_to_csv(videos)
    search_competitor_channels("요리 브이로그")
    # send_weekly_report()  # 주간 리포트 이메일 발송
