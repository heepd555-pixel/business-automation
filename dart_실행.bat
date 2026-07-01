@echo off
chcp 65001 > nul
echo.
echo  DART 재무 스크리너 실행 중...
echo.
python dart_screener.py
echo.
echo  완료. 아무 키나 누르면 닫힙니다.
pause > nul
