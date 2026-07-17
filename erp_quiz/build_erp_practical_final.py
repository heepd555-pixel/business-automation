# -*- coding: utf-8 -*-
"""ERP실기(회계2급/인사2급) 최종 레코드를 questions.json 스키마로 변환해서 병합."""
import json

SRC = r"C:\Users\heepd\.claude\jobs\232b699b\tmp\erp_practical_2g_final.json"
QFILE = "questions.json"


def main():
    with open(SRC, encoding="utf-8") as f:
        data = json.load(f)

    out = []
    for q in data:
        out.append({
            "id": f"ERP실기|{q['subject']}|{q['level']}|{q['round']}|{q['num']}",
            "exam": "ERP실기",
            "subject": q["subject"],
            "level": q["level"],
            "round": q["round"],
            "num": q["num"],
            "type": "practical",
            "keyword": q["keyword"],
            "unit": q["category"],
            "stem": q["stem"],
            "options": q["options"],
            "answer": q["answer"],
            "explanation": q["explanation"],
            "images": q["images"],
        })

    with open(QFILE, encoding="utf-8") as f:
        existing = json.load(f)
    existing = [x for x in existing if x.get("exam") != "ERP실기"]
    merged = existing + out
    with open(QFILE, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"ERP실기 {len(out)}문항 병합 -> 총 {len(merged)}문제")


if __name__ == "__main__":
    main()
