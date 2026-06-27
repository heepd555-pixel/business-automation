# 업무 자동화 패키지 🤖

> 소상공인 · 1인 크리에이터를 위한 Python 업무 자동화 솔루션

---

## 어떤 문제를 해결하나요?

| Before | After |
|--------|-------|
| 주문마다 직접 카카오 메시지 발송 | 주문 즉시 자동 발송 |
| 매일 아침 날씨/환율 직접 확인 | 매일 8시 자동 요약 발송 |
| 3개 쇼핑몰 따로 주문 확인 | 한 번에 통합 수집 |
| 경쟁사 가격 수동으로 체크 | 키워드 입력 한 번으로 자동 수집 |
| 인스타/트위터 각각 접속해서 발행 | 한 번 작성 → 동시 발행 |
| 유튜브 채널 성과 수동 기록 | 매주 자동 리포트 이메일 발송 |

---

## 기능 목록

### 📧 커뮤니케이션 자동화
- **이메일 자동 발송** — Gmail 기반, HTML 이메일 지원
- **카카오 알림톡 발송** — 주문 확인, 배송 알림 등
- **Slack 알림** — 업무 채널에 자동 메시지 발송

### 🛒 커머스 연동
- **스마트스토어 + 쿠팡 + 카페24** 주문 통합 수집
- 수집 완료 후 이메일 요약 자동 발송

### 📊 데이터 수집 및 분석
- **경쟁사 가격 수집** — 네이버 쇼핑 + 쿠팡 파트너스 API
- **날씨 / 환율 / 뉴스** 자동 수집
- **Google Sheets 대시보드** — 매출 현황 자동 업데이트

### 📱 SNS 자동화
- **인스타그램** 게시물 발행 + 성과 조회
- **트위터/X** 자동 포스팅 + 쓰레드 작성
- **멀티 SNS 동시 발행** — 한 번 작성 → 여러 플랫폼 동시 발행
- **콘텐츠 스케줄러** — Google Sheets 기반 예약 발행

### 🎬 유튜브 분석
- 채널 통계 자동 수집 (구독자, 조회수, 좋아요)
- 영상별 성과 분석 + CSV 저장
- 경쟁 채널 비교 분석
- 매주 리포트 이메일 자동 발송

### 🗂 업무 도구 연동
- **Notion** 업무일지 자동 생성
- **Google Calendar** 일정 조회 + 추가
- **모닝 브리핑** — 오늘 일정을 Slack + Notion에 자동 정리

---

## 기술 스택

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![Google API](https://img.shields.io/badge/Google%20API-Sheets%2FCalendar%2FYouTube-4285F4?style=flat&logo=google&logoColor=white)
![Meta API](https://img.shields.io/badge/Meta%20API-Instagram-0866FF?style=flat&logo=instagram&logoColor=white)
![Twitter API](https://img.shields.io/badge/Twitter%20API-v2-000000?style=flat&logo=x&logoColor=white)

```
Python 3.10+
├── requests          # API 통신
├── gspread           # Google Sheets 연동
├── google-auth       # Google 인증
├── google-api-python-client  # YouTube / Calendar
├── schedule          # 자동 스케줄 실행
├── python-dotenv     # 환경변수 관리
└── requests-oauthlib # Twitter OAuth 인증
```

---

## 파일 구조

```
📦 업무 자동화 패키지
├── 📄 .env                        API 키 관리 (비공개)
├── 📄 scheduler.py                전체 자동화 통합 실행
│
├── 📁 커뮤니케이션
│   ├── email_sender.py            이메일 자동 발송
│   ├── kakao_sender.py            카카오 알림톡
│   └── work_tool_integration.py   Slack / Notion / 캘린더
│
├── 📁 커머스
│   └── commerce_automation.py     스마트스토어 + 쿠팡 + 카페24
│
├── 📁 데이터 수집
│   ├── competitor_crawler.py      경쟁사 가격 수집
│   ├── external_data_collector.py 날씨 / 환율 / 뉴스
│   ├── sheets_dashboard.py        매출 대시보드
│   └── sheets_email_sender.py     시트 → 이메일 연동
│
└── 📁 SNS / 크리에이터
    ├── instagram_scheduler.py     인스타그램 자동화
    ├── twitter_automation.py      트위터 자동화
    ├── sns_multi_post.py          멀티 SNS 동시 발행
    ├── content_scheduler.py       콘텐츠 예약 발행
    └── youtube_analytics.py       유튜브 채널 분석
```

---

## 시작하기

### 1. 패키지 설치
```bash
pip install requests gspread google-auth google-api-python-client schedule python-dotenv requests-oauthlib
```

### 2. API 키 설정
`.env.example` 파일을 복사해 `.env`로 저장 후 키 입력:
```bash
cp .env.example .env
```

### 3. 실행
```bash
# 개별 실행
python email_sender.py
python youtube_analytics.py

# 전체 자동화 실행
python scheduler.py
```

---

## 자동 실행 스케줄

| 시간 | 실행 내용 |
|------|---------|
| 매일 08:00 | 모닝 브리핑 (Slack + Notion) |
| 매일 09:00 | 커머스 주문 통합 수집 + 이메일 발송 |
| 매일 09:10 | 날씨 / 환율 / 뉴스 수집 |
| 매 1분 | 콘텐츠 예약 발행 확인 |
| 매주 월 09:00 | 유튜브 주간 리포트 이메일 |
| 매주 월 09:30 | 경쟁사 가격 수집 |

---

## 외주 문의

업종과 필요한 자동화 기능을 알려주시면 맞춤 견적 드립니다.

- 📧 이메일: your_email@gmail.com
- 💬 카카오톡 오픈채팅: (링크)

---

## 라이선스

개인/상업적 사용 가능. 코드 무단 재배포 금지.
