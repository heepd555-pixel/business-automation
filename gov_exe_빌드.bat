@echo off
chcp 65001 > nul
echo.
echo  .exe 파일 빌드 중...
echo  (처음 실행 시 1~3분 소요됩니다)
echo.

pip install pyinstaller > nul 2>&1

pyinstaller --onefile --windowed --name "정부지원사업수집기" ^
  --add-data "gov_설정.json;." ^
  --add-data ".env;." ^
  gov_ui.py

echo.
echo  완료! dist 폴더에 정부지원사업수집기.exe 파일이 생성됐습니다.
echo.
pause
