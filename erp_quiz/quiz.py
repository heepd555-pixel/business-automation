# -*- coding: utf-8 -*-
"""
quiz.py -- ERP 정보관리사 기출문제 퀴즈 (참고용 학습 도구)

extract.py 가 만들어둔 questions.json (1,909문제)에서 조건에 맞는 문제를
무작위로 뽑아 4지선다 퀴즈를 봅니다. 정답을 입력하면 맞았는지/틀렸는지와
해설(있는 경우)을 바로 보여주고, 마지막에 점수와 틀린 문제 목록을 정리해줍니다.
틀린 문제는 wrong_log.json 에 쌓여서 --review 로 오답만 다시 풀 수 있습니다.

[ 사용법 ]
    python quiz.py                              # 전체 문제 중 무작위 20문제
    python quiz.py --count 10                   # 문제 수 지정
    python quiz.py --subject 회계 --level 1급    # 과목/급수 필터
    python quiz.py --type theory                 # 이론만 (practical 은 실무(더존))
    python quiz.py --round "2026년 5월 기출문제"  # 특정 회차만
    python quiz.py --review                      # 예전에 틀렸던 문제만 재출제
    python quiz.py --list                        # 과목/급수/회차 목록만 보기
"""
import argparse
import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_FILE = os.path.join(BASE_DIR, "questions.json")
WRONG_LOG_FILE = os.path.join(BASE_DIR, "wrong_log.json")

TYPE_LABEL = {"theory": "이론", "practical": "실무(더존)"}


def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        raise FileNotFoundError(
            f"{QUESTIONS_FILE} 가 없습니다. 먼저 'python extract.py' 를 실행해 문제를 추출하세요."
        )
    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_wrong_ids():
    if not os.path.exists(WRONG_LOG_FILE):
        return set()
    with open(WRONG_LOG_FILE, encoding="utf-8") as f:
        return set(json.load(f))


def save_wrong_ids(ids):
    with open(WRONG_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def show_catalog(questions):
    subjects = sorted({f"{q['subject']}{q['level']}" for q in questions})
    rounds = sorted({q['round'] for q in questions})
    print("=== 과목/급수 ===")
    print(", ".join(subjects))
    print("\n=== 회차 ===")
    print(", ".join(rounds))
    print("\n=== 유형 ===")
    print("theory(이론), practical(실무-더존)")


def filter_questions(questions, args, wrong_ids=None):
    result = []
    for q in questions:
        if not q.get("answer"):
            continue   # 정답 없는 문제(사례형 등)는 채점 불가하므로 제외
        if args.subject and q["subject"] != args.subject:
            continue
        if args.level and q["level"] != args.level:
            continue
        if args.type and q["type"] != args.type:
            continue
        if args.round and q["round"] != args.round:
            continue
        if wrong_ids is not None and q["id"] not in wrong_ids:
            continue
        result.append(q)
    return result


def run_quiz(pool, count):
    random.shuffle(pool)
    picked = pool[:count]
    if not picked:
        print("조건에 맞는 문제가 없습니다. 필터를 완화해보세요 (--list 로 사용 가능한 값 확인).")
        return

    correct, wrong = 0, []
    total = len(picked)
    for i, q in enumerate(picked, start=1):
        print(f"\n[{i}/{total}] ({TYPE_LABEL[q['type']]} | {q['subject']}{q['level']} | {q['round']})")
        if q.get("unit"):
            print(f"  {q['unit']}" + (f" -- 키워드: {q['keyword']}" if q.get("keyword") else ""))
        print(f"  Q. {q['stem']}")
        for num in ["1", "2", "3", "4"]:
            print(f"    {num}. {q['options'].get(num, '')}")

        ans = input("  답 (1-4, q=종료): ").strip()
        if ans.lower() == "q":
            print("\n중단합니다.")
            break

        if ans == q["answer"]:
            print("  정답입니다!")
            correct += 1
        else:
            print(f"  틀렸습니다. 정답은 {q['answer']}번 입니다.")
            wrong.append(q)
        if q.get("explanation"):
            print(f"  해설: {q['explanation']}")

    attempted = correct + len(wrong)
    print(f"\n=== 결과: {attempted}문제 중 {correct}개 정답 ({(correct/attempted*100 if attempted else 0):.0f}%) ===")

    if wrong:
        print("\n[틀린 문제]")
        for q in wrong:
            print(f"  - ({q['subject']}{q['level']}/{q['round']}) {q['stem'][:50]}...")

        existing = load_wrong_ids()
        existing.update(q["id"] for q in wrong)
        # 이번에 맞힌 문제는 오답노트에서 제거
        existing.difference_update(q["id"] for q in picked if q not in wrong)
        save_wrong_ids(existing)
        print(f"\n오답노트에 저장했습니다 ({WRONG_LOG_FILE}). 다음에 'python quiz.py --review' 로 다시 풀어보세요.")
    elif attempted:
        # 이번에 다 맞혔으면 오답노트에서도 제거
        existing = load_wrong_ids()
        existing.difference_update(q["id"] for q in picked)
        save_wrong_ids(existing)


def main():
    parser = argparse.ArgumentParser(description="ERP 정보관리사 기출문제 퀴즈")
    parser.add_argument("--count", type=int, default=20, help="문제 수 (기본 20)")
    parser.add_argument("--subject", type=str, default=None, help="회계/생산/인사/물류")
    parser.add_argument("--level", type=str, default=None, help="1급/2급")
    parser.add_argument("--type", type=str, choices=["theory", "practical"], default=None,
                         help="theory(이론) 또는 practical(실무-더존)")
    parser.add_argument("--round", type=str, default=None, help='예: "2026년 5월 기출문제"')
    parser.add_argument("--review", action="store_true", help="예전에 틀렸던 문제만 재출제")
    parser.add_argument("--list", action="store_true", help="사용 가능한 과목/급수/회차 목록만 출력")
    args = parser.parse_args()

    questions = load_questions()

    if args.list:
        show_catalog(questions)
        return

    wrong_ids = load_wrong_ids() if args.review else None
    if args.review and not wrong_ids:
        print("오답노트가 비어있습니다. 먼저 퀴즈를 풀어서 틀린 문제를 쌓아보세요.")
        return

    pool = filter_questions(questions, args, wrong_ids)
    run_quiz(pool, args.count)


if __name__ == "__main__":
    main()
