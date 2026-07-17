# -*- coding: utf-8 -*-
"""
extract_erp_practical_v2.py -- 회계2급/인사2급 실무문항(더존 시뮬레이션)을 화면 캡처
이미지까지 포함해서 추출한다.

extract_erp_practical.py 와 다른 점: HWP 안에 tr(문제/보기/정답)과 나란히 박혀있는
<img src="bindata/BIN....bmp"> 를 "이 미 지" 표시 위치 기준으로 각 문제에 정확히
매칭해서, 실제 더존 화면 캡처를 문제마다 함께 뽑아낸다. BMP는 용량이 커서(1~3MB)
JPEG로 변환해 static/images/ 에 저장한다.

[ 사용법 ]
    python extract_erp_practical_v2.py
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, ".")
import extract  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402
from PIL import Image  # noqa: E402

VERSION_RE_FIXED = re.compile(r'^버전\s*(.*?)\s*키워드\s*(.*?)\s*정답\s*([①②③④]|\d+)\s*$')
IMAGES_OUT_DIR = os.path.join(extract.BASE_DIR, "static", "images", "erp_practical")
CATEGORY_STRIP_RE = {
    "회계": re.compile(r"\s*회계[12]급\s*\d+\s*번\s*$"),
    "인사": re.compile(r"\s*인사[12]급\s*\d+\s*번\s*$"),
}


def category(unit, subject):
    pat = CATEGORY_STRIP_RE.get(subject)
    return pat.sub("", unit).strip() if pat else unit


def parse_with_images(html_path, img_dir, safe_round, subject, level):
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # 문서 순서대로 tr / img 를 같이 훑는다 (이미지가 어느 문제 바로 뒤에 있는지 위치로 판단)
    elems = soup.find_all(["tr", "img"])
    texts = []  # list of ("tr", text) or ("img", src)
    for e in elems:
        if e.name == "img":
            texts.append(("img", e.get("src")))
        else:
            t = e.get_text(" ", strip=True)
            if t:
                texts.append(("tr", t))

    n = len(texts)
    results = []
    i = 0
    img_seq = 0
    while i < n:
        kind, val = texts[i]
        if kind != "tr" or not VERSION_RE_FIXED.match(val):
            i += 1
            continue
        version, keyword, raw_answer = VERSION_RE_FIXED.match(val).groups()
        answer = extract.CIRCLE_TO_NUM.get(raw_answer, raw_answer)
        header = texts[i - 1][1] if i - 1 >= 0 and texts[i - 1][0] == "tr" else ""
        qm = extract.HEADER_NUM_RE.search(header)
        qnum = int(qm.group(1)) if qm else None

        j = i + 1
        qtext_parts = []
        while j < n and not (texts[j][0] == "tr" and texts[j][1] == "이 미 지") \
                and not (texts[j][0] == "tr" and VERSION_RE_FIXED.match(texts[j][1])):
            if texts[j][0] == "tr":
                qtext_parts.append(texts[j][1])
            j += 1
        qtext = " ".join(qtext_parts)

        images_for_q = []
        if j < n and texts[j][0] == "tr" and texts[j][1] == "이 미 지":
            j += 1
            while j < n and texts[j][0] == "img":
                img_seq += 1
                bmp_rel = texts[j][1]  # e.g. bindata/BIN0001.bmp
                bmp_path = os.path.join(os.path.dirname(html_path), bmp_rel)
                if os.path.exists(bmp_path):
                    fname = f"{safe_round}_{subject}{level}_{qnum}_{img_seq}.jpg"
                    dst = os.path.join(img_dir, fname)
                    try:
                        with Image.open(bmp_path) as im:
                            im.convert("RGB").save(dst, "JPEG", quality=85)
                        images_for_q.append(f"images/erp_practical/{fname}")
                    except Exception:
                        pass
                j += 1

        expl_parts = []
        while j < n and not (texts[j][0] == "tr" and VERSION_RE_FIXED.match(texts[j][1])):
            if texts[j][0] == "tr":
                t = texts[j][1]
                if extract.HEADER_NUM_RE.search(t) and len(t) < 40 and not t.startswith("문제"):
                    break
                expl_parts.append(t)
            j += 1
        explanation = " ".join(expl_parts).replace("문제 풀이", "").strip()

        parts = re.split(r"([①②③④])", qtext)
        stem = parts[0].replace("문제", "", 1).strip()
        options = {}
        for k in range(1, len(parts), 2):
            marker = parts[k]
            val2 = parts[k + 1] if k + 1 < len(parts) else ""
            options[extract.CIRCLE_TO_NUM[marker]] = val2.strip()

        if len(options) == 4 and qnum is not None:
            results.append({
                "num": qnum, "unit": header, "keyword": keyword.strip(" []"),
                "stem": stem, "options": options, "answer": answer,
                "explanation": explanation, "images": images_for_q,
            })
        i = j
    return results


def main():
    files = glob.glob(r"C:\Users\heepd\claude-test\erp\**\*실무문항*\*.hwp", recursive=True)
    files = sorted(set(
        f for f in files
        if (("회계2급" in os.path.basename(f)) or ("인사2급" in os.path.basename(f)))
    ))
    print(f"found {len(files)} files (회계2급/인사2급 only)")

    os.makedirs(IMAGES_OUT_DIR, exist_ok=True)

    all_records = []
    for idx, path in enumerate(files, 1):
        round_label, subject, level = extract.extract_meta(path)
        safe_round = re.sub(r"[^0-9A-Za-z가-힣]+", "_", round_label)
        print(f"{idx}/{len(files)} {round_label} {subject} {level}")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                html_path = extract.hwp_to_html(path, tmp)
                parsed = parse_with_images(html_path, IMAGES_OUT_DIR, safe_round, subject, level)
            for q in parsed:
                q["round"] = round_label
                q["subject"] = subject
                q["level"] = level
                q["category"] = category(q["unit"], subject)
            n_img = sum(1 for q in parsed if q["images"])
            print(f"  -> {len(parsed)} records, {n_img} with image")
            all_records.extend(parsed)
        except Exception as e:
            print(f"  FAIL {e}")

    print("total records", len(all_records))
    with open(r"C:\Users\heepd\.claude\jobs\232b699b\tmp\erp_practical_2g_with_images.json", "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
