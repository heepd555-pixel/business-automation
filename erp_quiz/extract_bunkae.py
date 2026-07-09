# -*- coding: utf-8 -*-
"""
extract_bunkae.py -- 전산회계1급/전산세무2급 확정답안 파일에서 "분개연습" 문제를 뽑아냄

실기시험(케이렙 프로그램 필요)은 지금까지 손대지 않았지만, 그 중 [일반전표입력]과
[결산정리] 문항은 실제로 프로그램 없이도 "거래를 보고 분개를 맞혀보는" 카드로 쓸 수
있다 (프로그램 조작이 필요 없고, 답이 텍스트로 완전히 표현됨). [매입매출전표입력]
문항은 전자세금계산서/카드영수증 이미지가 문제에 딸려 있어서 텍스트만으로는 문제
지문이 깨지므로 제외한다.

원본은 이미 extract_jsanhoe.py / extract_jstax.py 가 내려받아둔 "확정답안"(PDF, 최근
회차) / "답안"(HWP, 오래된 회차) 파일 그대로 재사용한다 (새로 다운로드하지 않음).

[ 사용법 ]
    python extract_bunkae.py --merge-into questions.json
"""
import argparse
import glob
import json
import os
import re
import sys
import tempfile
import zipfile

import fitz  # pymupdf

from extract_jsanhoe import _fix_mojibake, find_pair, hwp_to_soup, ROUND_RE

SOURCES = [
    ("전산회계1급", r"C:\Users\heepd\claude-test\전산회계1급_기출문제", "확정답안", "답안"),
    ("전산세무2급", r"C:\Users\heepd\claude-test\전산세무2급_기출문제", "확정답안", "답안"),
]

FATTAT_SOURCES = [
    ("FAT1급", r"C:\Users\heepd\claude-test\FAT1급_기출문제"),
    ("TAT2급", r"C:\Users\heepd\claude-test\TAT2급_기출문제"),
]

SECTION_RE = re.compile(r"\n\s*문제\s*\d+\s*\n")
FOOTER_RE = re.compile(r"\[제\d+회[^\]]*\]\n\d+/\d+\(뒷면 계속\)\n?")

BLOCK_RE_PDF = re.compile(
    r"\[(\d+)\]\s*(.+?)\n\[답\]\s*일반전표입력\s*\n(.+?)(?=\n\[\d+\]\s|\Z)", re.S
)
BLOCK_RE_HWP = re.compile(
    r"\[(\d+)\]\s*(.+?)\n\s*\[\s*답\s*\]\s*(.+?)(?=\n\s*\[\d+\]|\Z)", re.S
)
BLOCK_RE_FATTAT = re.compile(
    r"자료설명\s*\n(.+?)\n\s*평가문제.*?해답\s*및\s*풀이\s*\n.?\s*\n?\[일반전표입력\]\s*([\d\s월일]+?)\s*\n\s*(?:-?\s*분개\s*[:：]\s*)?(.+?)"
    r"(?=\n.{0,30}?\(\d+점\)|\n자료설명|\n해답\s*및\s*풀이|\n\[|\n한국공인회계사회|\n제\d+회|\n문제\s*\d|\Z)",
    re.S,
)


# ---------- 계정과목 -> 자산/부채/자본/수익/비용 분류 (결합관계·풀이 설명용) ----------
# 순서 중요: 더 구체적인(긴) 키워드를 먼저 검사해야 "감가상각누계액"이
# "감가상각비"로 잘못 매칭되는 일이 없다.
ACCOUNT_RULES = [
    # 자산의 차감계정(대변이 정상잔액, 늘어날수록 순자산은 줄어듦)
    ("대손충당금", "자산차감"), ("감가상각누계액", "자산차감"),
    # 비용
    ("매출원가", "비용"), ("복리후생비", "비용"), ("여비교통비", "비용"), ("접대비", "비용"),
    ("통신비", "비용"), ("수도광열비", "비용"), ("전력비", "비용"), ("세금과공과금", "비용"),
    ("세금과공과", "비용"), ("감가상각비", "비용"), ("지급임차료", "비용"), ("임차료", "비용"),
    ("수선비", "비용"), ("보험료", "비용"), ("차량유지비", "비용"), ("운반비", "비용"),
    ("도서인쇄비", "비용"), ("소모품비", "비용"), ("지급수수료", "비용"), ("수수료비용", "비용"),
    ("광고선전비", "비용"), ("이자비용", "비용"), ("기부금", "비용"), ("잡손실", "비용"),
    ("재해손실", "비용"), ("유형자산처분손실", "비용"), ("매출채권처분손실", "비용"),
    ("기타의대손상각비", "비용"), ("대손상각비", "비용"), ("무형자산상각비", "비용"),
    ("외환차손", "비용"), ("외화환산손실", "비용"), ("단기매매증권처분손실", "비용"),
    ("단기매매증권평가손실", "비용"), ("재고자산감모손실", "비용"), ("급여", "비용"),
    ("임금", "비용"), ("상여금", "비용"), ("퇴직급여", "비용"), ("잡급", "비용"),
    ("교육훈련비", "비용"), ("법인세비용", "비용"), ("법인세등", "비용"), ("법인세 등", "비용"),
    # 수익
    ("제품매출", "수익"), ("상품매출", "수익"), ("매출", "수익"), ("이자수익", "수익"),
    ("배당금수익", "수익"), ("임대료", "수익"), ("수수료수익", "수익"),
    ("유형자산처분이익", "수익"), ("자산수증이익", "수익"), ("채무면제이익", "수익"),
    ("잡이익", "수익"), ("외환차익", "수익"), ("외화환산이익", "수익"),
    ("단기매매증권처분이익", "수익"), ("단기매매증권평가이익", "수익"), ("대손충당금환입", "수익"),
    # 부채
    ("외상매입금", "부채"), ("지급어음", "부채"), ("미지급배당금", "부채"),
    ("미지급법인세", "부채"), ("미지급세금", "부채"), ("미지급비용", "부채"), ("미지급금", "부채"),
    ("부가세예수금", "부채"), ("예수금", "부채"), ("선수수익", "부채"), ("선수금", "부채"),
    ("유동성장기부채", "부채"), ("외화장기차입금", "부채"), ("장기차입금", "부채"),
    ("단기차입금", "부채"), ("사채", "부채"), ("퇴직급여충당부채", "부채"),
    ("퇴직연금충당부채", "부채"), ("임대보증금", "부채"), ("가수금", "부채"),
    # 자본
    ("자본금", "자본"), ("주식발행초과금", "자본"), ("자본잉여금", "자본"),
    ("이월이익잉여금", "자본"), ("이익잉여금", "자본"), ("이익준비금", "자본"),
    ("자기주식", "자본"), ("주식할인발행차금", "자본"), ("매도가능증권평가이익", "자본"),
    ("매도가능증권평가손실", "자본"), ("자본조정", "자본"),
    # 자산
    ("보통예금", "자산"), ("당좌예금", "자산"), ("정기예금", "자산"), ("정기적금", "자산"),
    ("단기매매증권", "자산"), ("매도가능증권", "자산"), ("만기보유증권", "자산"),
    ("외상매출금", "자산"), ("받을어음", "자산"), ("미수수익", "자산"), ("미수금", "자산"),
    ("선급비용", "자산"), ("선급금", "자산"), ("장기대여금", "자산"), ("단기대여금", "자산"),
    ("대여금", "자산"), ("가지급금", "자산"), ("원재료", "자산"), ("재공품", "자산"),
    ("저장품", "자산"), ("소모품", "자산"), ("상품", "자산"), ("제품", "자산"), ("토지", "자산"),
    ("건설중인자산", "자산"), ("건물", "자산"), ("기계장치", "자산"), ("차량운반구", "자산"),
    ("구축물", "자산"), ("비품", "자산"), ("영업권", "자산"), ("산업재산권", "자산"),
    ("특허권", "자산"), ("상표권", "자산"), ("개발비", "자산"), ("투자부동산", "자산"),
    ("부도어음과수표", "자산"), ("선납세금", "자산"), ("임차보증금", "자산"),
    ("부가세대급금", "자산"), ("퇴직연금운용자산", "자산"), ("현금과부족", "자산"),
    ("당좌수표", "자산"), ("현금", "자산"),
]
_NORMAL_SIDE = {"자산": "차", "비용": "차", "부채": "대", "자본": "대", "수익": "대", "자산차감": "대"}


_ACCOUNT_RULES_SORTED = sorted(ACCOUNT_RULES, key=lambda kc: -len(kc[0]))


def classify_account(name):
    # 키워드 길이가 긴(구체적인) 것부터 검사해야 "외상매출금"이 목록 순서상
    # 먼저 나오는 "매출"(수익) 규칙에 잘못 걸리는 일이 없다.
    key = re.sub(r"\s+", "", name)
    for keyword, category in _ACCOUNT_RULES_SORTED:
        if keyword in key:
            return category
    return None


def _side_label(category, side):
    increase = side == _NORMAL_SIDE[category]
    if category == "자산차감":
        return "자산의 감소" if increase else "자산의 증가"
    if category in ("자산", "부채", "자본"):
        return f"{category}의 " + ("증가" if increase else "감소")
    if category == "수익":
        return "수익의 발생" if increase else "수익의 감소"
    return "비용의 발생" if increase else "비용의 감소"


def build_combo_and_explanation(entries):
    """entries: [(side, '계정명 금액원'), ...] (균형 보정 이후). 결합관계 라벨과
    각 계정을 자산/부채/자본/수익/비용으로 분류한 풀이 설명을 만든다."""
    tagged = []
    labels_cha, labels_dae = [], []
    for side, text in entries:
        acct = re.sub(r"[\d,]+\s*원.*$", "", text).strip()
        acct = re.sub(r"\(.*?\)", "", acct).strip() or text.strip()
        category = classify_account(acct)
        if category:
            # 반품/취소 등으로 금액이 음수(-)면 정상 방향과 반대 효과이므로
            # 차/대 라벨을 뒤집는다 (예: (차) 외상매출금 -8,800,000원 은
            # 실제로는 외상매출금이 "감소"한 것).
            eff_side = side
            if re.search(r"-\s*[\d,]+\s*원", text):
                eff_side = "대" if side == "차" else "차"
            label = _side_label(category, eff_side)
            (labels_cha if side == "차" else labels_dae).append(label)
            tagged.append(f"({side}) {text.strip()} → {label}")
        else:
            tagged.append(f"({side}) {text.strip()}")

    combo = None
    if labels_cha or labels_dae:
        uniq_cha = list(dict.fromkeys(labels_cha))
        uniq_dae = list(dict.fromkeys(labels_dae))
        combo = " / ".join(uniq_cha + uniq_dae)

    explanation = "\n".join(tagged) if any("→" in t for t in tagged) else ""
    return combo, explanation


def _difficulty(entries, scenario):
    """차변/대변 줄 수, 시나리오 길이로 대략적인 난이도(하/중/상)를 매긴다."""
    n_lines = len(entries)
    if n_lines <= 2 and len(scenario) < 120:
        return "하"
    if n_lines <= 4 and len(scenario) < 250:
        return "중"
    return "상"


def _round_label(base):
    m = ROUND_RE.search(base)
    if m:
        return f"{m.group(1)}회"
    special_m = re.search(r"(특별회\d*)", base)
    return special_m.group(1) if special_m else base


# ---------- 차변/대변 금액 균형 보정 ----------
# 원본이 표가 아니라 들여쓰기로만 열을 맞춘 평문이라, 마커((차)/(대)) 없이 이어지는
# 줄(예: 두 번째 차변 계정)이 파싱 과정에서 엉뚱한 쪽에 붙는 경우가 있다. 복식부기는
# 항상 차변합계==대변합계이므로, 안 맞으면 뒤쪽 항목을 반대편으로 옮겨보면서 균형이
# 맞는 조합을 찾는다.

def _amount(text):
    # 계정명 바로 뒤에 오는 첫 "숫자원"을 금액으로 본다. 끝에 고정하면 "(거래처:
    # ...)" 같은 부연설명이 금액 뒤에 붙었을 때 못 찾는다.
    m = re.search(r"([\d,]+)\s*원", text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _balance_correct(entries):
    def totals(es):
        cha = sum(_amount(t) or 0 for s, t in es if s == "차")
        dae = sum(_amount(t) or 0 for s, t in es if s == "대")
        return cha, dae

    cha, dae = totals(entries)
    if cha == dae and cha != 0:
        return entries
    for k in range(1, min(3, len(entries)) + 1):
        trial = [e[:] for e in entries]
        for j in range(1, k + 1):
            trial[-j][0] = "차" if trial[-j][0] == "대" else "대"
        c2, d2 = totals(trial)
        if c2 == d2 and c2 != 0:
            return trial
    return entries


def _render_entries(entries):
    return "\n".join(f"({s}) {t}" for s, t in entries)


def _split_multi_account(text):
    """한 줄에 "계정명 금액원" 쌍이 여러 개 이어붙은 경우(마커 없이 같은 쪽
    계정이 여러 개일 때) 각각 분리한다. 못 쪼개면 원본 그대로 1개로 반환."""
    parts = re.findall(r".+?[\d,]+\s*원", text)
    if len(parts) <= 1:
        return [text]
    consumed = sum(len(p) for p in parts)
    tail = text[consumed:].strip()
    if tail:
        parts[-1] = parts[-1] + " " + tail
    parts = [p.strip() for p in parts]
    # 다음 항목 맨 앞에 붙은 "(거래처: ...)" 같은 괄호 설명은 실제로는 바로 앞
    # 항목에 대한 부연이므로 앞 항목 뒤로 옮긴다.
    fixed = [parts[0]]
    for p in parts[1:]:
        m = re.match(r"^(\([^)]*\))\s*(.+)$", p)
        if m:
            fixed[-1] += " " + m.group(1)
            p = m.group(2)
        fixed.append(p)
    return fixed


_FOOTNOTE_RE = re.compile(r"^(또는|[*×$])|×.*=|결산자료입력|전표추가|해당란에|입력하고")
_FOOTNOTE_START_RE = re.compile(r"[*×$]|결산자료입력|전표추가|해당란에")


def _append_entry(group, side, text):
    # "6,000,000원 × 9/12 = 4,500,000원"처럼 계산 각주 안에 있는 숫자가
    # split_multi_account에 의해 별도 계정 항목으로 오인되지 않도록, 각주가
    # 시작되는 지점부터는 통째로 떼어내 마지막 항목의 부연으로 붙인다.
    note = None
    m = _FOOTNOTE_START_RE.search(text)
    if m:
        text, note = text[: m.start()].strip(), text[m.start():].strip()

    for part in _split_multi_account(text):
        if not part.strip():
            continue
        if _FOOTNOTE_RE.search(part) and group:
            group[-1][1] += " " + part
        else:
            group.append([side, part])

    if note and group:
        group[-1][1] += " " + note


# ---------- PDF 경로 ----------

def clean_answer_pdf(raw):
    raw = FOOTER_RE.sub("", raw)
    raw = re.sub(r"(\(차\)|\(대\))", r"\n\1\n", raw).strip()
    lines = [l.strip() for l in raw.split("\n") if l.strip()]
    if not lines:
        return ""
    date_line = lines[0] if re.match(r"^\d{4}\.", lines[0]) else None
    body = lines[1:] if date_line else lines

    step1 = []
    for line in body:
        if line == "원" and step1:
            for j in range(len(step1) - 1, -1, -1):
                if re.fullmatch(r"[\d,]+", step1[j]):
                    step1[j] = step1[j] + "원"
                    break
            continue
        step1.append(line)

    merged = []
    i = 0
    while i < len(step1):
        line = step1[i]
        if line in ("(차)", "(대)", "또는") or re.match(r"^\d{4}\.", line) or line.startswith("ㆍ"):
            merged.append(line)
            i += 1
            continue
        if (
            i + 1 < len(step1)
            and re.fullmatch(r"[\d,]+\s*원?", step1[i + 1])
            and not re.search(r"\d", line)
        ):
            amt = step1[i + 1].replace(" ", "")
            if not amt.endswith("원"):
                amt += "원"
            merged.append(f"{line} {amt}")
            i += 2
        else:
            merged.append(line)
            i += 1

    # 또는(대안 분개) 단위로 끊어서 각각 따로 균형 보정
    groups = [[]]
    side = None
    for line in merged:
        if line in ("(차)", "(대)"):
            side = "차" if line == "(차)" else "대"
            continue
        if line == "또는":
            groups.append([])
            side = None
            continue
        if side:
            _append_entry(groups[-1], side, line)
        elif groups[-1]:
            # 계정/금액이 아닌 부가 설명(ㆍ...) 등은 마지막 항목에 붙여서 보존
            groups[-1][-1][1] += " " + line

    out_parts = []
    first_entries = None
    for g in groups:
        if not g:
            continue
        corrected = _balance_correct(g)
        if first_entries is None:
            first_entries = corrected
        out_parts.append(_render_entries(corrected))

    body_text = ("\n\n[또는]\n").join(out_parts)
    return (date_line + "\n" if date_line else "") + body_text, (first_entries or [])


def parse_pdf(answer_pdf_path):
    doc = fitz.open(answer_pdf_path)
    full_text = "".join(p.get_text() for p in doc)
    doc.close()

    results = []
    for chunk in SECTION_RE.split(full_text):
        for m in BLOCK_RE_PDF.finditer(chunk):
            num, scenario, raw_ans = m.groups()
            cleaned, entries = clean_answer_pdf(raw_ans)
            if "(차)" not in cleaned or "(대)" not in cleaned:
                continue
            scenario = FOOTER_RE.sub("", scenario).strip()
            scenario = re.sub(r"\s*\n\s*", " ", scenario).strip()
            results.append((scenario, cleaned, entries))
    return results


# ---------- HWP 경로 ----------

def clean_answer_hwp(raw):
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = re.sub(r"\s*(\(차\)|\(대\))\s*", r"\n\1", raw).strip()
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    groups = [[]]
    side = None
    for line in lines:
        if line.startswith("(차)") or line.startswith("(대)"):
            side = "차" if line.startswith("(차)") else "대"
            line = line[3:].strip()
        if line == "또는" or line.startswith("또는 "):
            groups.append([])
            side = None
            rest = line[len("또는"):].strip()
            if rest:
                groups[-1].append([None, rest])
            continue
        if side:
            _append_entry(groups[-1], side, line)
        elif groups[-1]:
            groups[-1][-1][1] += " " + line

    out_parts = []
    first_entries = None
    for g in groups:
        g = [[s, t] for s, t in g if s]
        if not g:
            continue
        corrected = _balance_correct(g)
        if first_entries is None:
            first_entries = corrected
        out_parts.append(_render_entries(corrected))

    return ("\n\n[또는]\n").join(out_parts), (first_entries or [])


def parse_hwp(answer_hwp_path, tmp_dir):
    soup = hwp_to_soup(answer_hwp_path, tmp_dir)
    full_text = soup.get_text("\n")

    results = []
    for chunk in SECTION_RE.split(full_text):
        for m in BLOCK_RE_HWP.finditer(chunk):
            num, scenario, raw_ans = m.groups()
            if "매입매출전표입력" in raw_ans:
                continue
            cleaned, entries = clean_answer_hwp(raw_ans)
            if "(차)" not in cleaned or "(대)" not in cleaned:
                continue
            scenario = re.sub(r"\s*\n\s*", " ", scenario).strip()
            results.append((scenario, cleaned, entries))
    return results


# ---------- FAT1급/TAT2급 경로 (한국공인회계사회 형식) ----------

def clean_answer_fattat(raw):
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = re.sub(r"\s*(\(차\)|\(대\))\s*", r"\n\1", raw).strip()
    lines = [l.strip() for l in raw.split("\n") if l.strip()]

    groups = [[]]
    side = None
    for line in lines:
        if line.startswith("(차)") or line.startswith("(대)"):
            side = "차" if line.startswith("(차)") else "대"
            line = line[3:].strip()
        if line == "또는" or line.startswith("또는 "):
            groups.append([])
            side = None
            continue
        if side:
            _append_entry(groups[-1], side, line)
        elif groups[-1]:
            groups[-1][-1][1] += " " + line

    out_parts = []
    first_entries = None
    for g in groups:
        g = [[s, t] for s, t in g if s]
        if not g:
            continue
        corrected = _balance_correct(g)
        if first_entries is None:
            first_entries = corrected
        out_parts.append(_render_entries(corrected))

    return ("\n\n[또는]\n").join(out_parts), (first_entries or [])


def parse_fattat(pdf_path):
    doc = fitz.open(pdf_path)
    full_text = "".join(p.get_text() for p in doc)
    doc.close()

    results = []
    for m in BLOCK_RE_FATTAT.finditer(full_text):
        scenario, date, raw_ans = m.groups()
        cleaned, entries = clean_answer_fattat(raw_ans)
        if "(차)" not in cleaned or "(대)" not in cleaned:
            continue
        scenario = re.sub(r"\s*\n\s*", " ", scenario).strip()
        results.append((scenario, cleaned, entries))
    return results


# ---------- 회차 처리 ----------

def process_round(round_zip_path, subject, answer_marker_pdf, answer_marker_hwp, tmp_dir_factory):
    base = os.path.basename(round_zip_path)
    round_label = _round_label(base)

    with tmp_dir_factory() as tmp:
        with zipfile.ZipFile(round_zip_path) as zf:
            fixed_names = [_fix_mojibake(n) for n in zf.namelist()]
        is_pdf = any("A형" in n and n.lower().endswith(".pdf") for n in fixed_names)

        if is_pdf:
            _, answer_file = find_pair(round_zip_path, tmp, "A형", answer_marker_pdf, "pdf")
            if not answer_file:
                return []
            pairs = parse_pdf(answer_file)
        else:
            _, answer_file = find_pair(round_zip_path, tmp, "A형", answer_marker_hwp, "hwp")
            if not answer_file:
                return []
            pairs = parse_hwp(answer_file, tmp)

        return _build_results(subject, round_label, pairs)


def process_round_fattat(pdf_path, subject):
    base = os.path.basename(pdf_path)
    round_label = _round_label(base)
    pairs = parse_fattat(pdf_path)
    return _build_results(subject, round_label, pairs)


def _entries_balanced(entries):
    cha = sum(_amount(t) or 0 for s, t in entries if s == "차")
    dae = sum(_amount(t) or 0 for s, t in entries if s == "대")
    return cha == dae and cha != 0


# 시나리오 지문에 "숫자 없이 원"만 남은 경우(원본 표/이미지의 금액이
# 텍스트 추출에서 빠진 경우) - 공백을 사이에 둔 정상 표기("1,050 원")는
# 제외하고, 진짜로 숫자가 아예 없는 경우만 잡는다.
_MISSING_AMOUNT_RE = re.compile(r"(?<![0-9,]) 원(을|이|의|에|정도)?(?=\s|$)")


def _scenario_bad(scenario):
    if "[답]" in scenario or re.search(r"\[\d+\]", scenario):
        return True
    if _MISSING_AMOUNT_RE.search(scenario):
        return True
    return False


def _build_results(subject, round_label, pairs):
    results = []
    num = 0
    for scenario, answer_text, entries in pairs:
        # 균형 보정을 거쳤는데도 차변/대변 합계가 안 맞으면 파싱이 깨진 것이므로
        # 잘못된 정답을 보여주느니 아예 제외한다. 시나리오에 정답 마커가 섞여
        # 들어갔거나 금액 숫자가 통째로 빠진 경우도 마찬가지로 제외한다.
        if not _entries_balanced(entries) or _scenario_bad(scenario):
            continue
        num += 1
        combo, explanation = build_combo_and_explanation(entries)
        results.append({
            "id": f"분개연습|{subject}|{round_label}|{num}",
            "exam": "분개연습",
            "subject": subject,
            "level": _difficulty(entries, scenario),
            "combo": combo,
            "type": "bunkae",
            "round": round_label,
            "num": num,
            "stem": scenario,
            "answer_text": answer_text,
            "explanation": explanation,
            "answer": "correct",
        })
    return results


def main():
    parser = argparse.ArgumentParser(description="분개연습 문제 -> questions.json 항목 변환")
    parser.add_argument("--merge-into", required=True)
    args = parser.parse_args()

    all_new = []
    for subject, source_dir, marker_pdf, marker_hwp in SOURCES:
        zips = sorted(glob.glob(os.path.join(source_dir, "*.zip")))
        print(f"[{subject}] 회차 zip {len(zips)}개 발견")
        for zpath in zips:
            try:
                results = process_round(
                    zpath, subject, marker_pdf, marker_hwp, tempfile.TemporaryDirectory,
                )
            except Exception as e:
                print(f"  !! {os.path.basename(zpath)}: 처리 실패 - {e}", file=sys.stderr)
                results = []
            print(f"  {os.path.basename(zpath)}: {len(results)}문항")
            all_new.extend(results)

    for subject, source_dir in FATTAT_SOURCES:
        pdfs = sorted(glob.glob(os.path.join(source_dir, "*.pdf")))
        print(f"[{subject}] 회차 pdf {len(pdfs)}개 발견")
        for ppath in pdfs:
            try:
                results = process_round_fattat(ppath, subject)
            except Exception as e:
                print(f"  !! {os.path.basename(ppath)}: 처리 실패 - {e}", file=sys.stderr)
                results = []
            print(f"  {os.path.basename(ppath)}: {len(results)}문항")
            all_new.extend(results)

    with open(args.merge_into, encoding="utf-8") as f:
        existing = json.load(f)
    existing = [q for q in existing if q.get("exam") != "분개연습"]

    merged = existing + all_new
    with open(args.merge_into, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n분개연습 {len(all_new)}문항 추가 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
