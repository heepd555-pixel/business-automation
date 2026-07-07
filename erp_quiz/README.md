# 📘 ERP 정보관리사 기출문제 퀴즈

기출문제 HWP 파일(이론문항 + 실무문항(더존))에서 문제·보기·정답·해설을 자동으로
뽑아내고, 터미널에서 바로 풀어볼 수 있는 개인 학습용 퀴즈 도구입니다.

- 대상: 회계/생산/인사/물류 × 1급/2급, 2025년 7월 ~ 2026년 5월 (총 6회차)
- 문제 수: 1,909문제 (이론 1,054 + 실무(더존) 855)
- 영림원 실무문제는 다루지 않습니다 (요청에 따라 더존만 처리)

---

## 폴더 구조

```
erp_quiz/
├── extract.py        ← HWP 시험지를 questions.json 으로 변환 (pyhwp 사용)
├── quiz.py           ← 실제로 문제를 풀어보는 CLI 퀴즈
├── web_app.py        ← 휴대폰 브라우저로 풀 수 있는 웹앱 버전 (Flask)
├── templates/        ← web_app.py 가 쓰는 화면 (base/setup/quiz/summary.html)
├── quiz_exe_빌드.bat  ← 파이썬 없는 컴퓨터에서도 돌아가는 .exe 빌드 스크립트
├── questions.json    ← 추출된 문제 은행 (커밋됨, extract.py 재실행 없이 바로 사용 가능)
├── wrong_log.json    ← 오답노트 (자동 생성/갱신, 커밋 안 됨)
└── erp_source/       ← 원본 HWP/DOCX 시험 자료 (커밋 안 됨, 저작권 있는 원본이라 제외)
```

## 사용법

### 1. 문제 풀기 (questions.json 이 이미 있으므로 바로 실행 가능)
```bash
python quiz.py                              # 전체 문제 중 무작위 20문제
python quiz.py --count 10                   # 문제 수 지정
python quiz.py --subject 회계 --level 1급    # 과목/급수 필터
python quiz.py --type theory                # 이론만 (practical = 실무(더존))
python quiz.py --round "2026년 5월 기출문제" # 특정 회차만
python quiz.py --review                     # 예전에 틀렸던 문제만 재출제
python quiz.py --list                       # 사용 가능한 과목/급수/회차 목록 보기
```
문제를 보고 1~4 중 답을 입력하면 정답 여부와 해설(있는 경우)을 바로 보여주고,
틀린 문제는 `wrong_log.json`에 자동으로 쌓여서 다음에 `--review`로 다시 풀 수 있습니다.

### 2. 문제 은행 다시 만들기 (원본 HWP 파일을 바꿨을 때만 필요)
```bash
pip install pyhwp beautifulsoup4
python extract.py                # erp_source/ 전체를 다시 읽어서 questions.json 갱신
python extract.py --limit 3      # 파일 3개만 처리 (테스트용, 빠름)
```

### 3. 파이썬 없는 컴퓨터에서도 실행할 .exe 만들기
```bash
quiz_exe_빌드.bat
```
`dist\ERP기출문제퀴즈.exe` 와 `dist\questions.json` 두 파일이 생성됩니다.
**이 둘은 항상 같은 폴더에 있어야 합니다** (exe 가 옆에서 questions.json 을 찾습니다).
이 두 파일만 복사해서 옮기면 파이썬이 설치되지 않은 다른 Windows 컴퓨터에서도
더블클릭으로 바로 실행됩니다. (오답노트 `wrong_log.json` 도 exe 옆에 자동 생성됩니다.)

### 4. 휴대폰 브라우저로 풀기 (웹앱)
```bash
pip install flask
python web_app.py
```
실행하면 콘솔에 두 개의 주소가 뜹니다:
- `http://127.0.0.1:5000` -- 이 컴퓨터에서 확인용
- `http://192.168.x.x:5000` -- **같은 와이파이에 연결된 휴대폰**에서 이 주소를 브라우저에 입력

휴대폰에서 접속한 뒤 브라우저 메뉴에서 **"홈 화면에 추가"**를 하면 아이콘이 생겨서
앱처럼 쓸 수 있습니다 (실제 설치형 앱은 아니고, 컴퓨터가 켜져 있고 `web_app.py`가
실행 중일 때만 접속됩니다 -- 외부 인터넷에는 공개되지 않고 같은 공유기 안에서만 동작).

## 문제 데이터의 한계

- 이론문제 중 일부(초반 사례형/개념형 문제 236개)는 원본 학습자료 자체에 정답이
  표기되어 있지 않아 채점 대상에서 제외됩니다.
- 실무(더존) 문제는 실제로는 ERP 프로그램을 조작해서 값을 조회해야 풀 수 있는
  시뮬레이션 문제입니다. 이 도구는 문제와 보기, 정답, (있는 경우) 해설만 보여줄 뿐
  실제 더존 iCUBE 프로그램을 시뮬레이션하지는 않습니다 -- 실제 조작 연습은 별도로 하세요.
- 문제 안의 이미지(스크린샷, 도표)는 텍스트로 추출되지 않고 "이미지"로 생략됩니다.
