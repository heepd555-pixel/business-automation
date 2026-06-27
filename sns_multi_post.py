# 멀티 SNS 동시 발행 (인스타그램 + 트위터 + 슬랙)
# 한 번 작성하면 여러 플랫폼에 동시 발행
import os
from dotenv import load_dotenv
from instagram_scheduler import upload_image, publish_post
from twitter_automation import post_tweet
from work_tool_integration import send_slack

load_dotenv()

def post_to_all(text, image_url=None, platforms=None):
    """
    여러 SNS에 동시 발행
    platforms: ["instagram", "twitter", "slack"] 중 선택
    """
    if platforms is None:
        platforms = ["instagram", "twitter", "slack"]

    results = {}

    print(f"\n🚀 멀티 SNS 발행 시작")
    print(f"   내용: {text[:50]}...")
    print(f"   플랫폼: {', '.join(platforms)}\n")

    if "instagram" in platforms:
        if image_url:
            try:
                container_id = upload_image(image_url, text)
                post_id = publish_post(container_id)
                results["instagram"] = {"status": "성공", "id": post_id}
            except Exception as e:
                results["instagram"] = {"status": "실패", "error": str(e)}
        else:
            results["instagram"] = {"status": "건너뜀", "reason": "이미지 없음 (인스타는 이미지 필수)"}
            print("⚠️  인스타그램: 이미지 URL이 없어 건너뜀")

    if "twitter" in platforms:
        try:
            tweet_text = text[:280]  # 트위터 280자 제한
            tweet_id = post_tweet(tweet_text)
            results["twitter"] = {"status": "성공", "id": tweet_id}
        except Exception as e:
            results["twitter"] = {"status": "실패", "error": str(e)}

    if "slack" in platforms:
        try:
            send_slack(f"📢 새 콘텐츠 발행\n{text}")
            results["slack"] = {"status": "성공"}
        except Exception as e:
            results["slack"] = {"status": "실패", "error": str(e)}

    print(f"\n📊 발행 결과 요약")
    for platform, result in results.items():
        status = "✅" if result["status"] == "성공" else "❌"
        print(f"  {status} {platform}: {result['status']}")

    return results

def post_schedule_from_list(content_list):
    """
    콘텐츠 목록을 순서대로 발행
    content_list: [{"text": "내용", "image_url": "URL", "platforms": ["twitter"]}, ...]
    """
    print(f"\n📅 예약 콘텐츠 {len(content_list)}개 발행 시작\n")
    for i, content in enumerate(content_list, 1):
        print(f"[{i}/{len(content_list)}]")
        post_to_all(
            text=content["text"],
            image_url=content.get("image_url"),
            platforms=content.get("platforms", ["twitter", "slack"])
        )
        print()

if __name__ == "__main__":
    # 사용 예시
    post_to_all(
        text="오늘의 콘텐츠입니다 🔥 #크리에이터 #자동화",
        image_url="https://example.com/image.jpg",
        platforms=["instagram", "twitter", "slack"]
    )
