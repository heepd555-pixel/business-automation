@echo off
chcp 65001 > nul
echo.
echo  정부 지원사업 통합 수집기 실행 중...
echo.
python gov_support.py
echo.
echo  완료. 아무 키나 누르면 닫힙니다.
pause > nul
