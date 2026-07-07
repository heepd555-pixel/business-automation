@echo off
chcp 65001 > nul
echo.
echo  ERP 퀴즈 .exe 빌드 중...
echo  (처음 실행 시 1~3분 소요됩니다)
echo.

pip install pyinstaller > nul 2>&1

pyinstaller --onefile --name "ERP기출문제퀴즈" quiz.py

echo.
echo  questions.json 을 dist 폴더로 복사합니다 (exe 옆에 있어야 문제를 읽을 수 있음)...
copy /Y questions.json dist\questions.json > nul

echo.
echo  완료! dist 폴더의 "ERP기출문제퀴즈.exe" 를 questions.json 과 함께 옮기면
echo  파이썬 없는 컴퓨터에서도 그대로 실행됩니다 (둘은 항상 같은 폴더에 있어야 함).
echo.
pause
