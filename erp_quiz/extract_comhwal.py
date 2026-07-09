# -*- coding: utf-8 -*-
"""
extract_comhwal.py -- 컴퓨터활용능력 2급 필기 기출문제(comcbt.com, HWP)를
questions.json에 합칠 항목으로 변환.

이 시험은 필기(객관식, 컴�터 일반+스프레드시트 일반 각 20문항)와 실기
(엑셀/액세스 실제 조작)가 완전히 분리된 시험이라, 필기 문서 자체에
실기 내용이 안 섞여 있다 (다른 시험들처럼 실무 부분을 걸러낼 필요 없음).
정답은 별도 정답표 없이, 문제 안에서 채워진 원문자(❶❷❸❹)로 바로 표시된다.

[ 사용법 ]
    python extract_comhwal.py --source "../컴활2급_기출문제" --merge-into questions.json
"""
import argparse
import glob
import json
import os
import re
import subprocess

from bs4 import BeautifulSoup

HWP5HTML = r"C:\Users\heepd\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5html.exe"

EMPTY_TO_NUM = {"①": "1", "②": "2", "③": "3", "④": "4"}
FILLED_TO_NUM = {"❶": "1", "❷": "2", "❸": "3", "❹": "4"}
QSTART_RE = re.compile(r"\n(\d+)\.\s*")
ROUND_RE = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")


def hwp_to_text(hwp_path, tmp_dir):
    out = os.path.join(tmp_dir, "html_" + os.path.basename(hwp_path))
    subprocess.run([HWP5HTML, hwp_path, "--output", out], check=True, capture_output=True)
    with open(os.path.join(out, "index.xhtml"), encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    return soup.get_text("\n", strip=True)


def parse_questions(text):
    parts = QSTART_RE.split("\n" + text)
    results = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        markers = re.findall(r"[①②③④❶❷❸❹]", body)
        if len(markers) != 4:
            continue
        stem_m = re.search(r"[①②③④❶❷❸④❶❷❸❹]", body)
        stem = body[:stem_m.start()].strip() if stem_m else body.strip()
        chunks = re.split(r"[①②③④❶❷❸❹]", body)[1:]
        if len(chunks) != 4:
            continue
        answer = None
        options = {}
        for j, (marker, chunk) in enumerate(zip(markers, chunks)):
            options[str(j + 1)] = chunk.strip()
            if marker in FILLED_TO_NUM:
                answer = FILLED_TO_NUM[marker]
        if answer and len(options) == 4:
            results[num] = {"num": num, "stem": stem, "options": options, "answer": answer}
    return results


def process_round(hwp_path, tmp_dir_factory):
    with tmp_dir_factory() as tmp:
        text = hwp_to_text(hwp_path, tmp)

    round_m = ROUND_RE.search(text[:200])
    if round_m:
        round_label = f"{round_m.group(1)}년 {int(round_m.group(2))}월"
    else:
        round_label = os.path.basename(hwp_path)

    questions = parse_questions(text)
    results = []
    for num, q in questions.items():
        results.append({
            "id": f"컴활2급|{round_label}|theory|{num}",
            "exam": "컴활2급",
            "subject": "컴퓨터일반" if num <= 20 else "스프레드시트일반",
            "level": "2급",
            "type": "theory",
            "round": round_label,
            "num": num,
            "stem": q["stem"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": "",
        })
    return results


def main():
    import tempfile

    parser = argparse.ArgumentParser(description="컴활2급 기출문제(HWP) -> questions.json 항목 변환")
    parser.add_argument("--source", required=True)
    parser.add_argument("--merge-into", required=True)
    args = parser.parse_args()

    files = sorted(glob.glob(os.path.join(args.source, "*.hwp")))
    print(f"회차 HWP {len(files)}개 발견")

    all_new = []
    for path in files:
        try:
            results = process_round(path, tempfile.TemporaryDirectory)
        except Exception as e:
            print(f"  !! {os.path.basename(path)}: 처리 실패 - {e}")
            results = []
        print(f"  {os.path.basename(path)}: {len(results)}문제")
        all_new.extend(results)

    with open(args.merge_into, encoding="utf-8") as f:
        existing = json.load(f)
    for q in existing:
        q.setdefault("exam", "erp")
    existing = [q for q in existing if q.get("exam") != "컴활2급"]

    merged = existing + all_new
    with open(args.merge_into, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n컴활2급 {len(all_new)}문제 추가 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
