# -*- coding: utf-8 -*-
"""
extract_jstax.py -- 전산세무2급 기출문제(comcbt.com)를 questions.json에 합칠 항목으로 변환

전산회계1급과 발행 기관(한국세무사회)·형식(PDF/HWP, A형/확정답안)이 완전히
같아서 extract_jsanhoe.py의 파싱 함수를 그대로 재사용하고, 회차/과목 라벨만
전산세무2급용으로 바꾼다.

[ 사용법 ]
    python extract_jstax.py --source "../전산세무2급_기출문제" --merge-into questions.json
"""
import argparse
import glob
import json
import os
import re
import zipfile

from extract_jsanhoe import (
    ROUND_RE,
    _fix_mojibake,
    extract_answers_hwp,
    extract_answers_pdf,
    extract_explanations_hwp,
    extract_explanations_pdf,
    extract_theory_text_pdf,
    find_pair,
    hwp_to_soup,
    parse_questions_hwp,
    parse_questions_pdf,
)

EXAM = "전산세무2급"
SUBJECT = "전산세무"
LEVEL = "2급"


def process_round(round_zip_path, tmp_dir_factory):
    base = os.path.basename(round_zip_path)
    round_m = ROUND_RE.search(base)
    if round_m:
        round_label = f"{round_m.group(1)}회"
    else:
        special_m = re.search(r"(특별회\d*)", base)
        round_label = special_m.group(1) if special_m else base

    with tmp_dir_factory() as tmp:
        with zipfile.ZipFile(round_zip_path) as zf:
            fixed_names = [_fix_mojibake(n) for n in zf.namelist()]
        is_pdf = any("A형" in n and n.lower().endswith(".pdf") for n in fixed_names)

        if is_pdf:
            a_form, answer_file = find_pair(round_zip_path, tmp, "A형", "확정답안", "pdf")
            if not a_form or not answer_file:
                print(f"  !! {round_label}: A형/확정답안 PDF 못찾음")
                return []
            questions = parse_questions_pdf(extract_theory_text_pdf(a_form))
            answers = extract_answers_pdf(answer_file)
            explanations = extract_explanations_pdf(answer_file)
        else:
            a_form, answer_file = find_pair(round_zip_path, tmp, "A형", "답안", "hwp")
            if not a_form or not answer_file:
                print(f"  !! {round_label}: A형/답안 HWP 못찾음")
                return []
            questions = parse_questions_hwp(hwp_to_soup(a_form, tmp))
            answer_soup = hwp_to_soup(answer_file, tmp)
            answers = extract_answers_hwp(answer_soup)
            explanations = extract_explanations_hwp(answer_soup)

        results = []
        for num, q in questions.items():
            results.append({
                "id": f"{EXAM}|{round_label}|theory|{num}",
                "exam": EXAM,
                "subject": SUBJECT,
                "level": LEVEL,
                "type": "theory",
                "round": round_label,
                "num": num,
                "stem": q["stem"],
                "options": q["options"],
                "answer": answers.get(num),
                "explanation": explanations.get(num, ""),
            })
        return results


def main():
    import tempfile

    parser = argparse.ArgumentParser(description="전산세무2급 기출문제 -> questions.json 항목 변환")
    parser.add_argument("--source", required=True)
    parser.add_argument("--merge-into", required=True)
    args = parser.parse_args()

    zips = sorted(glob.glob(os.path.join(args.source, "*.zip")))
    print(f"회차 zip {len(zips)}개 발견")

    all_new = []
    for zpath in zips:
        try:
            results = process_round(zpath, tempfile.TemporaryDirectory)
        except Exception as e:
            print(f"  !! {os.path.basename(zpath)}: 처리 실패 - {e}")
            results = []
        print(f"  {os.path.basename(zpath)}: {len(results)}문제 (정답 있음 {sum(1 for r in results if r['answer'])}개)")
        all_new.extend(results)

    with open(args.merge_into, encoding="utf-8") as f:
        existing = json.load(f)
    for q in existing:
        q.setdefault("exam", "erp")
    existing = [q for q in existing if q.get("exam") != EXAM]

    merged = existing + all_new
    with open(args.merge_into, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n{EXAM} {len(all_new)}문제 추가 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
