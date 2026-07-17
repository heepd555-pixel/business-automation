# -*- coding: utf-8 -*-
"""
fix_practical_language.py -- 분개연습에서 두 가지를 정리:

1) 스템만 봐서는 풀 수 없는(원본 프로그램에 이미 입력된 값을 "조회"해야만
   나오는 숫자에 의존하는) 문제 3개를 제거. README의 "실기(프로그램 조작
   필요)는 다루지 않는다"는 원칙을 위반하는 항목들이라 quiz.py의 자동 채점
   대상에 남겨두면 안 됨.

2) 답은 스템만으로 낼 수 있지만, "고정자산등록메뉴", "일반전표입력메뉴"처럼
   실제로는 존재하지 않는 이 앱의 화면을 가리키는 실기 프로그램 문구가
   남아있는 항목들의 스템 문구만 정리 (분개 내용/숫자는 그대로).

[ 사용법 ]
    python fix_practical_language.py --apply-to questions.json
"""
import argparse
import json

EXCLUDE_IDS = {
    # 6/30 부가세 회계처리를 "조회"해야만 나오는 미지급세금 9,724,000원이
    # 스템 어디에도 없음 -- 원본 답안 프로그램 데이터에만 있는 숫자.
    "분개연습|전산회계1급|84회|11",
    # 확정급여형(DB형) 퇴직연금운용자산의 기존 잔액을 몰라도 되는지 스템만
    # 봐서는 확정할 수 없음 (충당부채가 부족하면 다른 분개가 되어야 함).
    "분개연습|전산회계1급|88회|6",
    # 기존 주식할인발행차금 잔액 3,000,000원이 스템 어디에도 없음 -- 원본
    # 프로그램 장부에만 있는 숫자.
    "분개연습|전산세무2급|117회|2",
}

STEM_FIXES = {
    "분개연습|전산회계1급|98회|13":
        "기말 현재 보유하고 있는 감가상각대상자산은 다음과 같다. "
        "상각범위액을 계산하여 감가상각비로 반영하는 분개를 하시오.(3점)\n\n"
        "· 계정과목: 기계장치\n· 취득년월일: 2019년 7월 27일\n· 취득원가: 30,000,000원\n"
        "· 전기말감가상각누계액: 9,000,000원\n· 경비구분: 제조\n· 내용연수: 5년\n· 감가상각방법: 정률법",
    "분개연습|전산세무2급|74회|9":
        "12월 31일 현재 보유중인 제조부문의 감가상각대상 자산은 다음과 같다. 제시된 자료 이외에 "
        "감가상각대상자산은 없다고 가정하고, 감가상각금액을 계산(월할상각)하여 분개하시오. (3점)\n\n"
        "계정과목: 기계장치\n취득원가: 100,000,000원\n잔존가치: 0원\n내용연수: 5년\n"
        "전기말 감가상각누계액: 0원\n취득일자: 2017.7.1\n상각방법: 정률법\n상각률: 0.451",
    "분개연습|전산세무2급|55회|1":
        "1월 10일 다음은 ㈜세원의 보통예금 통장거래 내역이다. 선납세금 계정과목을 사용하여 "
        "분개하시오.(3점)\n\n"
        "일자: 1/10\n입금액: 86,000원\n"
        "내역: 예금결산이자는 100,000원이며, 이자소득세 14,000원을 제외한 순액으로 입금되었음",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-to", required=True)
    args = parser.parse_args()

    with open(args.apply_to, encoding="utf-8") as f:
        data = json.load(f)

    before = len(data)
    data = [q for q in data if q["id"] not in EXCLUDE_IDS]
    removed = before - len(data)

    by_id = {q["id"]: q for q in data}
    applied, missing = 0, []
    for qid, new_stem in STEM_FIXES.items():
        if qid in by_id:
            by_id[qid]["stem"] = new_stem
            applied += 1
        else:
            missing.append(qid)

    with open(args.apply_to, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"removed: {removed}, stem fixes applied: {applied}, missing: {len(missing)}, total now: {len(data)}")
    for m in missing:
        print("  MISSING:", m)


if __name__ == "__main__":
    main()
