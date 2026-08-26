# -*- coding: utf-8 -*-
"""
extract_jsanhoe.py -- 전산회계1급 기출문제(comcbt.com)를 questions.json에 합칠 항목으로 변환

회차별로 원본 형식이 다릅니다:
  - 최근 회차(대략 111회 이후): PDF (A형.pdf / 확정답안.pdf)
  - 오래된 회차(대략 110회 이전): HWP (A형.hwp / 답안.hwp)
두 형식 모두 이론시험(객관식 15문항)만 추출합니다. 실무시험은 실제 케이렙(KcLep)
회계프로그램으로 데이터를 입력해야 풀리는 시뮬레이션이라 ERP 실무문제와 같은 이유로
다루지 않습니다. A형/B형은 같은 15문제를 순서만 바꾼 것이라 A형만 사용합니다.

[ 사용법 ]
    python extract_jsanhoe.py --source "../전산회계1급_기출문제" --merge-into questions.json
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile

import fitz  # pymupdf
from bs4 import BeautifulSoup

HWP5HTML = r"C:\Users\heepd\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5html.exe"

CIRCLE_TO_NUM = {"①": "1", "②": "2", "③": "3", "④": "4"}
ROUND_RE = re.compile(r"(\d+)회")
QSTART_RE = re.compile(r"\n(\d+)\.\s*")
HEADER_FOOTER_RE = re.compile(r"\[제\d+회[^\]]*\]\n")
PAGE_FOOTER_RE = re.compile(r"\d+/\d+\(뒷면 계속\)\n?")
ANSWER_TABLE_RE = re.compile(
    r"A\s*형\s*\n?((?:<\d+>\s*\n?)+)"
    r"((?:[①②③④1-4]\s*(?:,\s*[①②③④1-4]\s*)*\n?){1,20})"
)


def _fix_mojibake(name):
    """오래된 zip은 파일명이 EUC-KR인데 UTF-8 플래그 없이 저장돼서
    Python zipfile이 cp437로 잘못 디코딩한다. 원래 바이트로 되돌려서
    cp949로 다시 디코딩하면 복구된다. 이미 정상(UTF-8)인 경우는 그대로 둠."""
    try:
        return name.encode("cp437").decode("cp949")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return name


def find_pair(round_zip_path, tmp_dir, a_marker, answer_marker, ext):
    a_form, answer = None, None
    with zipfile.ZipFile(round_zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            fixed_name = _fix_mojibake(info.filename)
            base = os.path.basename(fixed_name)
            if not base.lower().endswith(f".{ext}"):
                continue
            dest = os.path.join(tmp_dir, base)
            with zf.open(info) as src, open(dest, "wb") as dst:
                dst.write(src.read())
            if a_marker in base:
                a_form = dest
            elif answer_marker in base:
                answer = dest
    return a_form, answer


# ---------- PDF 경로 (최근 회차) ----------

def extract_theory_text_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = "".join(p.get_text() for p in doc)
    start_m = re.search(r"이\s*론\s*시\s*험", full_text)
    end_m = re.search(r"실\s*무\s*시\s*험", full_text)
    if not start_m or not end_m:
        return ""
    text = full_text[start_m.end():end_m.start()]
    text = HEADER_FOOTER_RE.sub("", text)
    text = PAGE_FOOTER_RE.sub("", text)
    return text


def parse_questions_pdf(theory_text):
    parts = QSTART_RE.split(theory_text)
    results = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        m = re.search(r"①\n②\n③\n④\n", body)
        if m:
            stem = body[:m.start()].strip()
            tail = body[m.end():].strip()
            lines = [o for o in tail.split("\n") if o.strip()]
            opts = _resolve_options(lines)
        else:
            # "①재무상태표" 처럼 마커+보기가 한 줄에 붙어있는 변형
            stem_m = re.search(r"①", body)
            stem = body[:stem_m.start()].strip() if stem_m else body.strip()
            opts = _resolve_from_merged_text([body])
        if opts:
            results[num] = {"num": num, "stem": stem, "options": opts}
    return results


def extract_answers_pdf(answer_pdf_path):
    doc = fitz.open(answer_pdf_path)
    text = doc[0].get_text()
    return _parse_answer_table(text)


def extract_explanations_pdf(answer_pdf_path):
    """확정답안 PDF는 표(정답 요약) 뒤에 문제별 [답] X 해설... 이 이어진다."""
    doc = fitz.open(answer_pdf_path)
    full_text = "".join(p.get_text() for p in doc)
    full_text = HEADER_FOOTER_RE.sub("", full_text)
    full_text = PAGE_FOOTER_RE.sub("", full_text)

    start_m = re.search(
        r"B\s*형\s*\n?(?:<\d+>\s*\n?)+(?:[①②③④1-4]\s*\n?)+", full_text,
    )
    if not start_m:
        return {}
    detail_text = full_text[start_m.end():]

    parts = QSTART_RE.split("\n" + detail_text)
    results = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        m = re.search(r"\[\s*답\s*\]\s*[①②③④1-4]\s*", body)
        if m:
            results[num] = body[m.end():].strip()
    return results


# ---------- HWP 경로 (오래된 회차) ----------

def hwp_to_soup(hwp_path, tmp_dir):
    out = os.path.join(tmp_dir, "html_" + os.path.basename(hwp_path))
    subprocess.run([HWP5HTML, hwp_path, "--output", out], check=True, capture_output=True)
    with open(os.path.join(out, "index.xhtml"), encoding="utf-8") as f:
        return BeautifulSoup(f, "html.parser")


THEORY_QUESTION_COUNT = 15  # 전산회계1급 이론시험은 항상 객관식 15문항


def parse_questions_hwp(soup):
    paras = soup.find_all("p")
    # "이론시험" 큰 제목이 없는(오래된) 회차도 있어서, 문제 첫머리 안내문구를 보조 기준으로 씀
    start_idx = next(
        (i for i, p in enumerate(paras)
         if "이론시험" in p.get_text() or "다음 문제를 보고 알맞은 것을 골라" in p.get_text()),
        None,
    )
    if start_idx is None:
        return {}

    # "실무시험" 표기 방식이 회차마다 달라 신뢰하기 어려워서, 대신 문항이
    # 정확히 15개(고정 문항수) 모이면 바로 멈춘다.
    blocks = []
    cur = None
    for p in paras[start_idx:]:
        if len(blocks) >= THEORY_QUESTION_COUNT:
            break
        cls = p.get("class") or []
        text = p.get_text(strip=True)
        if not text:
            continue
        if "Bullet-2" in cls:
            if cur:
                blocks.append(cur)
            cur = {"stem_parts": [text], "opt_paras": []}
        elif cur is not None:
            if any(re.match(r"Bullet-[3-9]", c) for c in cls):
                cur["opt_paras"].append(text)
            else:
                cur["stem_parts"].append(text)
    if cur and len(blocks) < THEORY_QUESTION_COUNT:
        blocks.append(cur)

    results = {}
    for num, q in enumerate(blocks, start=1):
        opts = _resolve_options(q["opt_paras"]) or _resolve_from_merged_text(q["stem_parts"])
        if opts:
            results[num] = {"num": num, "stem": q["stem_parts"][0], "options": opts}

    if not results:
        # 더 오래된 회차는 "Bullet-2" 스타일 대신, 문제 앞에 "1. " 처럼 번호가
        # 그냥 텍스트로 붙어있고 보기(①②③④)도 한 문단에 이어져 있음 (PDF 방식과 동일).
        theory_text = "\n".join(
            p.get_text(strip=True) for p in paras[start_idx:] if p.get_text(strip=True)
        )
        parts = QSTART_RE.split("\n" + theory_text)
        for i in range(1, len(parts), 2):
            num = int(parts[i])
            if num > THEORY_QUESTION_COUNT:
                continue
            body = parts[i + 1] if i + 1 < len(parts) else ""
            opts = _resolve_from_merged_text([body])
            if opts:
                stem = re.split(r"[①②③④]", body)[0].strip()
                results[num] = {"num": num, "stem": stem, "options": opts}
    return results


def extract_answers_hwp(soup):
    text = soup.get_text("\n", strip=True)
    return _parse_answer_table(text)


def extract_explanations_hwp(soup):
    """답안 HWP도 PDF와 같은 구조(B형 정답표 뒤에 문제별 [답] X 해설...)를 쓰는
    회차가 많아서 같은 방식으로 시도한다. 표/날짜가 섞여 있는 회차는 그냥 스킵됨."""
    text = soup.get_text("\n", strip=True)
    start_m = re.search(r"B\s*형\s*\n?(?:<\d+>\s*\n?)+(?:[①②③④1-4]\s*\n?)+", text)
    if not start_m:
        return {}
    detail_text = text[start_m.end():]

    parts = QSTART_RE.split("\n" + detail_text)
    results = {}
    for i in range(1, len(parts), 2):
        num = int(parts[i])
        body = parts[i + 1] if i + 1 < len(parts) else ""
        m = re.search(r"\[\s*답\s*\]\s*[①②③④1-4]\s*", body)
        if m:
            results[num] = body[m.end():].strip()
    return results


# ---------- 공통 ----------

def _resolve_options(lines):
    if len(lines) == 4:
        return {str(i + 1): v.strip() for i, v in enumerate(lines)}
    if len(lines) == 8:
        # 2단 표(예: 빈칸 채우기 (가)/(나)) -- 같은 인덱스끼리 이어붙임
        return {str(i + 1): f"{lines[i]} / {lines[i + 4]}".strip() for i in range(4)}
    return None


def _resolve_from_merged_text(stem_parts):
    merged = " ".join(stem_parts)
    m = re.findall(r"[①②③④][^①②③④]+", merged)
    if len(m) >= 4 and len(m) % 4 == 0:
        return {str(i + 1): m[i][1:].strip() for i in range(4)}
    return None


def _parse_answer_table(text):
    m = ANSWER_TABLE_RE.search(text)
    if not m:
        return {}
    nums = re.findall(r"<(\d+)>", m.group(1))
    # 복수정답 인정 문항은 "①,③" 처럼 쉼표로 묶여 나온다. 한 문항 몫을 통째로
    # 잡아서 "1,3" 으로 저장한다 (web_app 이 쉼표로 나눠서 채점).
    marks = re.findall(r"[①②③④1-4](?:\s*,\s*[①②③④1-4])*", m.group(2))
    answers = [
        ",".join(CIRCLE_TO_NUM.get(c, c) for c in re.findall(r"[①②③④1-4]", mk))
        for mk in marks
    ]  # 원문자 또는 이미 숫자인 경우 둘 다 처리
    return {int(n): a for n, a in zip(nums, answers)}


def process_round(round_zip_path):
    base = os.path.basename(round_zip_path)
    round_m = ROUND_RE.search(base)
    if round_m:
        round_label = f"{round_m.group(1)}회"
    else:
        # "특별회", "특별회2" 처럼 숫자 없는 회차명 (예: 코로나19 시기 보충시험)
        special_m = re.search(r"(특별회\d*)", base)
        round_label = special_m.group(1) if special_m else base

    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(round_zip_path) as zf:
            fixed_names = [_fix_mojibake(n) for n in zf.namelist()]
        # 설치안내 PDF 등 부수 파일 때문에 오탐하지 않도록 "A형" 이름을 가진
        # 실제 시험지가 .pdf 인지 .hwp 인지로 판단한다.
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
                "id": f"전산회계1급|{round_label}|theory|{num}",
                "exam": "전산회계1급",
                "subject": "전산회계",
                "level": "1급",
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
    parser = argparse.ArgumentParser(description="전산회계1급 기출문제 -> questions.json 항목 변환")
    parser.add_argument("--source", required=True, help="전산회계1급_기출문제 zip들이 있는 폴더")
    parser.add_argument("--merge-into", required=True, help="합칠 questions.json 경로")
    args = parser.parse_args()

    zips = sorted(glob.glob(os.path.join(args.source, "*.zip")))
    print(f"회차 zip {len(zips)}개 발견")

    all_new = []
    for zpath in zips:
        try:
            results = process_round(zpath)
        except Exception as e:
            print(f"  !! {os.path.basename(zpath)}: 처리 실패 - {e}", file=sys.stderr)
            results = []
        print(f"  {os.path.basename(zpath)}: {len(results)}문제 (정답 있음 {sum(1 for r in results if r['answer'])}개)")
        all_new.extend(results)

    with open(args.merge_into, encoding="utf-8") as f:
        existing = json.load(f)
    for q in existing:
        q.setdefault("exam", "erp")
    existing = [q for q in existing if q.get("exam") != "전산회계1급"]  # 재실행 시 중복 방지

    merged = existing + all_new
    with open(args.merge_into, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n전산회계1급 {len(all_new)}문제 추가 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
