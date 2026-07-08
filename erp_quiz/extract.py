# -*- coding: utf-8 -*-
"""
extract.py -- erp_source/ 안의 HWP 시험 문제 파일들을 읽어서 questions.json 으로 변환

[ 이 파일이 하는 일 ]
ERP 정보관리사 기출문제(이론문항 + 실무문항(더존))는 한글(HWP) 파일이라 그대로는
컴퓨터가 읽기 어렵습니다. 이 스크립트는:
  1) pyhwp(hwp5html)로 각 HWP 파일을 HTML로 변환
  2) HTML 표 구조를 분석해서 문제/보기/정답/해설을 뽑아냄
  3) 전부 모아서 questions.json 하나로 저장
그러면 quiz.py 가 questions.json 만 읽어서 빠르게 퀴즈를 낼 수 있습니다.

[ 문서 구조 차이 -- 왜 이론/실무를 다르게 파싱하나 ]
  이론문항: 문제 하나가 표의 <tr> 하나에 통째로 들어있음
            "문제 N. 스템 ①..④ 문제풀이및계산식 [설명]...[정답] X"
  실무문항(더존): 문제 하나가 <tr> 여러 개(헤더/버전·정답/문제·보기/이미지/해설)로 나뉘어 있고,
            정답이 원 숫자(①)가 아니라 그냥 숫자(1~4)로 별도 표시됨
            "ERP {과정명} {과목}{급수} N번" / "버전 ... 키워드 ... 정답 X" / "문제 ... ①..④" / "이미지" / "문제 풀이 ..."

[ 사용법 ]
    python extract.py                 # erp_source/ 전체를 스캔해서 questions.json 생성
    python extract.py --limit 3       # 파일 3개만 처리 (테스트용, 빠름)
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import tempfile

from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.join(BASE_DIR, "erp_source")
OUTPUT_FILE = os.path.join(BASE_DIR, "questions.json")

HWP5HTML = r"C:\Users\heepd\AppData\Local\Python\pythoncore-3.14-64\Scripts\hwp5html.exe"

SUBJECT_LEVEL_RE = re.compile(r'(회계|생산|인사|물류)(\d)급')
ROUND_RE = re.compile(r'(\d{4})년\s*(\d+)월')

QSTART_RE = re.compile(r'^문제\s*(\d+)\.\s*')
SOLUTION_SPLIT_RE = re.compile(r'문제\s*풀이\s*및\s*계\s*산\s*식')
ANSWER_RE = re.compile(r'(?:\[\s*설명\s*\]\s*(.*?))?\[\s*정답\s*\]\s*([①②③④])', re.DOTALL)

VERSION_RE = re.compile(r'^버전\s*(.*?)\s*키워드\s*(.*?)\s*정답\s*(\d+)\s*$')
HEADER_NUM_RE = re.compile(r'(\d+)\s*번\s*$')

CIRCLE_TO_NUM = {'①': '1', '②': '2', '③': '3', '④': '4'}


def find_files():
    """erp_source/ 를 훑어서 (theory 파일 목록, practical(더존) 파일 목록) 반환.

    연도별로 폴더/파일명 규칙이 제각각이라(예: "이론문제_..." vs "...이론.hwp"
    vs "이론(공통)_...") 폴더명이 아니라 파일명에 "이론"/"실무"가 있는지로
    판단한다. 인코딩이 깨진 파일명(예: 오래된 zip의 EUC-KR/CP437 혼선)은
    "이론"/"실무" 글자 자체가 안 남아있어서 자연히 걸러진다."""
    theory, practical = [], []
    for path in glob.glob(os.path.join(SOURCE_DIR, "**", "*.hwp"), recursive=True):
        norm = path.replace("\\", "/")
        name = os.path.basename(path)
        if "영림원" in norm:
            continue
        if "이론" in name:
            theory.append(path)
        elif "실무" in name:
            practical.append(path)
    return sorted(theory), sorted(practical)


ROUND_NUM_RE = re.compile(r'(\d{4})년\s*0?(\d)회')          # "2023년 01회 기출문제"
PAREN_MONTH_RE = re.compile(r'\((\d{1,2})월')                # "...(1월, 100회)"
YEAR_RE = re.compile(r'(\d{4})년')

# 이 시험은 매년 홀수월(1/3/5/7/9/11월)에 회차가 매겨져서 진행된다.
# "2023년 01회" 처럼 폴더/파일명에 월이 아예 안 적힌 경우, 회차 번호로부터
# 월을 역산한다 (1회->1월, 2회->3월, ... 6회->11월).
ROUND_TO_MONTH = {1: 1, 2: 3, 3: 5, 4: 7, 5: 9, 6: 11}


def extract_meta(path):
    """파일 경로에서 (round_label, subject, level) 뽑아내기.

    폴더명 규칙이 연도마다 달라서("2025년 7월 기출문제" / "2023년 01회 기출문제" /
    "2022년 11월 기출문제(06회)" 등) 폴더명만으로는 정렬 가능한 "YYYY년 M월
    기출문제" 형태를 항상 못 뽑는다. 폴더명 + 파일명을 합쳐서 최대한 월 정보를
    찾아내고, 그래도 못 찾으면 회차 번호(홀수월 6회 시행 규칙)로 역산한다."""
    norm = path.replace("\\", "/")
    parts = norm.split("/")
    src_idx = parts.index("erp_source") if "erp_source" in parts else 0
    folder = parts[src_idx + 1] if src_idx + 1 < len(parts) else ""
    name = os.path.basename(path)
    combined = f"{folder} {name}"

    round_label = folder
    ym = ROUND_RE.search(combined)
    if ym:
        round_label = f"{ym.group(1)}년 {int(ym.group(2))}월 기출문제"
    else:
        year_m = YEAR_RE.search(combined)
        month_m = PAREN_MONTH_RE.search(combined)
        if year_m and month_m:
            round_label = f"{year_m.group(1)}년 {int(month_m.group(1))}월 기출문제"
        else:
            rm = ROUND_NUM_RE.search(combined)
            if rm and int(rm.group(2)) in ROUND_TO_MONTH:
                round_label = f"{rm.group(1)}년 {ROUND_TO_MONTH[int(rm.group(2))]}월 기출문제"

    sm = SUBJECT_LEVEL_RE.search(name)
    subject, level = (sm.group(1), sm.group(2) + "급") if sm else ("알수없음", "")
    return round_label or "", subject, level


def hwp_to_html(hwp_path, out_dir):
    subprocess.run(
        [HWP5HTML, hwp_path, "--output", out_dir],
        check=True, capture_output=True,
    )
    return os.path.join(out_dir, "index.xhtml")


def parse_theory(html_path):
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')

    results = []
    for tr in soup.find_all('tr'):
        text = tr.get_text(' ', strip=True)
        m = QSTART_RE.match(text)
        if not m:
            continue
        qnum = int(m.group(1))
        rest = text[m.end():]

        sm = SOLUTION_SPLIT_RE.search(rest)
        options_region, tail_region = (rest[:sm.start()], rest[sm.end():]) if sm else (rest, '')

        parts = re.split(r'([①②③④])', options_region)
        stem = parts[0].strip()
        options = {}
        for j in range(1, len(parts), 2):
            marker = parts[j]
            chunk = parts[j + 1] if j + 1 < len(parts) else ''
            options[CIRCLE_TO_NUM[marker]] = chunk.strip()

        explanation, answer = '', None
        am = ANSWER_RE.search(tail_region)
        if am:
            explanation = (am.group(1) or '').strip()
            answer = CIRCLE_TO_NUM[am.group(2)]

        if len(options) == 4:   # 보기 4개가 온전히 있는 것만 채택 (표/이미지형 문제는 제외)
            results.append({
                'num': qnum, 'stem': stem, 'options': options,
                'explanation': explanation, 'answer': answer,
            })
    return results


def parse_practical(html_path):
    with open(html_path, encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    texts = [tr.get_text(' ', strip=True) for tr in soup.find_all('tr')]
    texts = [t for t in texts if t]

    n = len(texts)
    results = []
    i = 0
    while i < n:
        vm = VERSION_RE.match(texts[i])
        if not vm:
            i += 1
            continue
        version, keyword, answer = vm.groups()
        header = texts[i - 1] if i - 1 >= 0 else ''
        qm = HEADER_NUM_RE.search(header)
        qnum = int(qm.group(1)) if qm else None

        j = i + 1
        qtext_parts = []
        while j < n and texts[j] != '이 미 지' and not VERSION_RE.match(texts[j]):
            qtext_parts.append(texts[j])
            j += 1
        qtext = ' '.join(qtext_parts)

        if j < n and texts[j] == '이 미 지':
            j += 1

        expl_parts = []
        while j < n and not VERSION_RE.match(texts[j]):
            if HEADER_NUM_RE.search(texts[j]) and len(texts[j]) < 40 and not texts[j].startswith('문제'):
                break
            expl_parts.append(texts[j])
            j += 1
        explanation = ' '.join(expl_parts).replace('문제 풀이', '').strip()

        parts = re.split(r'([①②③④])', qtext)
        stem = parts[0].replace('문제', '', 1).strip()
        options = {}
        for k in range(1, len(parts), 2):
            marker = parts[k]
            val = parts[k + 1] if k + 1 < len(parts) else ''
            options[CIRCLE_TO_NUM[marker]] = val.strip()

        if len(options) == 4 and qnum is not None:
            results.append({
                'num': qnum, 'unit': header, 'keyword': keyword, 'stem': stem,
                'options': options, 'answer': answer, 'explanation': explanation,
            })
        i = j
    return results


def process(paths, qtype, limit=None):
    all_qs = []
    paths = paths[:limit] if limit else paths
    total = len(paths)
    for idx, path in enumerate(paths, start=1):
        round_label, subject, level = extract_meta(path)
        name = os.path.basename(path)
        print(f"  [{qtype}] {idx}/{total} {round_label} {subject}{level} -- {name}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                html_path = hwp_to_html(path, tmp)
                parsed = parse_theory(html_path) if qtype == 'theory' else parse_practical(html_path)
            for q in parsed:
                q['type'] = qtype
                q['round'] = round_label
                q['subject'] = subject
                q['level'] = level
                q['id'] = f"{round_label}|{subject}{level}|{qtype}|{q['num']}"
            all_qs.extend(parsed)
        except Exception as e:
            print(f"    !! 변환 실패: {e}", file=sys.stderr)
    return all_qs


def main():
    parser = argparse.ArgumentParser(description="ERP 기출문제 HWP -> questions.json 변환")
    parser.add_argument("--limit", type=int, default=None, help="파일 개수 제한 (테스트용)")
    args = parser.parse_args()

    theory_files, practical_files = find_files()
    print(f"이론문항 파일: {len(theory_files)}개, 실무문항(더존) 파일: {len(practical_files)}개")

    questions = []
    questions += process(theory_files, 'theory', args.limit)
    questions += process(practical_files, 'practical', args.limit)

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

    print(f"\n총 {len(questions)}문제 추출 완료 -> {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
