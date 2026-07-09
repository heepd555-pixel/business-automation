# -*- coding: utf-8 -*-
"""
extract_tat.py -- TAT 2급 기출문제(comcbt.com + ad-hrd.net, 한국공인회계사회 원본)를
questions.json에 합칠 항목으로 변환. extract_fat.py와 발행기관·형식이 동일해서
파싱 로직을 그대로 복사해왔다 ([N] 문제번호, 해설\\n[정답] X 형식).

"실무수행평가"(회계프로그램 데이터입력 시뮬레이션)는 실제 프로그램 없이는
학습 의미가 없어서 "실무이론평가"(객관식)만 추출한다.

[ 사용법 ]
    python extract_tat.py --source "../TAT2급_기출문제" --merge-into questions.json
"""
import argparse
import glob
import json
import os
import re

import fitz  # pymupdf

CIRCLE_TO_NUM = {"①": "1", "②": "2", "③": "3", "④": "4"}
QSTART_RE = re.compile(r"\[(\d+)\]\s*")
ROUND_RE = re.compile(r"(\d+)회")


def extract_theory_text(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = "".join(p.get_text() for p in doc)

    # "실무이론평가"는 표지 안내문에도 한 번 더 나와서, 실제 문제 [1] 바로 앞의
    # (마지막) 등장 위치를 시작점으로 삼는다.
    first_q = re.search(r"\[1\]\s*\S", full_text)
    if not first_q:
        return ""
    start_candidates = list(re.finditer(r"실무이론평가", full_text[:first_q.start()]))
    if not start_candidates:
        return ""
    start_idx = start_candidates[-1].end()

    end_m = re.search(r"실무수행평가", full_text[first_q.start():])
    if not end_m:
        return ""
    end_idx = first_q.start() + end_m.start()

    if end_idx <= start_idx:
        return ""
    return full_text[start_idx:end_idx]


def parse_round(theory_text):
    parts = QSTART_RE.split(theory_text)
    results = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""

        m = re.search(r"해설\s*\n?\[\s*정답\s*\]\s*[①②③④1-4]\s*", body)
        if not m:
            continue
        qa_region = body[:m.start()]
        explanation = body[m.end():].strip()

        ans_m = re.search(r"\[\s*정답\s*\]\s*([①②③④1-4])", body)
        answer = CIRCLE_TO_NUM.get(ans_m.group(1), ans_m.group(1)) if ans_m else None

        opt_m = re.search(r"①", qa_region)
        if not opt_m:
            continue  # 원문자 자체가 없는(이미지 보기 등) 문제는 신뢰도 낮아 스킵
        stem = qa_region[:opt_m.start()].strip()
        opts_text = qa_region[opt_m.start():]
        matches = re.findall(r"[①②③④]([^①②③④]+)", opts_text)
        if len(matches) != 4:
            continue
        options = {str(i + 1): v.strip() for i, v in enumerate(matches)}

        if answer:
            results[num] = {
                "num": num, "stem": stem, "options": options,
                "answer": answer, "explanation": explanation,
            }
    return results


def process_round(pdf_path):
    round_m = ROUND_RE.search(os.path.basename(pdf_path))
    round_label = f"{round_m.group(1)}회" if round_m else os.path.basename(pdf_path)

    theory_text = extract_theory_text(pdf_path)
    if not theory_text:
        return []
    questions = parse_round(theory_text)

    results = []
    for num, q in questions.items():
        results.append({
            "id": f"TAT2급|{round_label}|theory|{num}",
            "exam": "TAT2급",
            "subject": "TAT",
            "level": "2급",
            "type": "theory",
            "round": round_label,
            "num": num,
            "stem": q["stem"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": q["explanation"],
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="FAT 1급 기출문제(PDF) -> questions.json 항목 변환")
    parser.add_argument("--source", required=True, help="TAT2급_기출문제 PDF들이 있는 폴더")
    parser.add_argument("--merge-into", required=True, help="합칠 questions.json 경로")
    args = parser.parse_args()

    pdfs = sorted(glob.glob(os.path.join(args.source, "*.pdf")))
    print(f"회차 PDF {len(pdfs)}개 발견")

    all_new = []
    for pdf_path in pdfs:
        results = process_round(pdf_path)
        print(f"  {os.path.basename(pdf_path)}: {len(results)}문제")
        all_new.extend(results)

    with open(args.merge_into, encoding="utf-8") as f:
        existing = json.load(f)
    for q in existing:
        q.setdefault("exam", "erp")
    existing = [q for q in existing if q.get("exam") != "TAT2급"]  # 재실행 시 중복 방지

    merged = existing + all_new
    with open(args.merge_into, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\nTAT2급 {len(all_new)}문제 추가 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
