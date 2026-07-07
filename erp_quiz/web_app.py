# -*- coding: utf-8 -*-
"""
web_app.py -- ERP 기출문제 퀴즈를 휴대폰 브라우저로 풀 수 있게 해주는 웹앱

quiz.py 의 문제 로딩/필터링/오답노트 로직을 그대로 재사용하고, 화면만
콘솔 대신 휴대폰 브라우저용 페이지로 바꾼 버전입니다. 진짜 설치형 앱은
아니지만, 같은 와이파이에 연결된 휴대폰에서 접속해서 "홈 화면에 추가"하면
아이콘이 생겨서 앱처럼 쓸 수 있습니다.

[ 사용법 ]
    pip install flask
    python web_app.py
    -> 화면에 뜨는 "휴대폰에서 접속할 주소" 를 휴대폰 브라우저에 입력

[ 참고 ]
이 서버는 같은 와이파이 안에서만 접속 가능합니다 (외부 인터넷에 공개되지 않음).
"""
import os
import random
import socket

from flask import Flask, redirect, render_template, request, session, url_for

from quiz import filter_questions, load_questions, load_wrong_ids, save_wrong_ids

app = Flask(__name__)
app.secret_key = os.urandom(24)   # 개인용 로컬 서버라 재시작하면 세션(진행중 퀴즈)은 초기화됨

QUESTIONS = load_questions()
TYPE_LABEL = {"theory": "이론", "practical": "실무(더존)"}


class _Args:
    """quiz.filter_questions() 는 argparse.Namespace 모양을 기대하므로 흉내만 냄."""
    def __init__(self, subject, level, qtype, round_):
        self.subject = subject or None
        self.level = level or None
        self.type = qtype or None
        self.round = round_ or None


def _catalog():
    subjects = sorted({q["subject"] for q in QUESTIONS})
    levels = sorted({q["level"] for q in QUESTIONS})
    rounds = sorted({q["round"] for q in QUESTIONS})
    return subjects, levels, rounds


def _local_ip():
    """같은 와이파이의 휴대폰이 접속할 이 PC의 사설 IP 주소를 추정."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


@app.route("/")
def setup():
    subjects, levels, rounds = _catalog()
    wrong_count = len(load_wrong_ids())
    return render_template(
        "setup.html", subjects=subjects, levels=levels, rounds=rounds,
        wrong_count=wrong_count,
    )


@app.route("/start", methods=["POST"])
def start():
    review = request.form.get("review") == "on"
    count = int(request.form.get("count") or 20)

    if review:
        wrong_ids = load_wrong_ids()
        pool = [q for q in QUESTIONS if q["id"] in wrong_ids and q.get("answer")]
    else:
        args = _Args(
            request.form.get("subject"), request.form.get("level"),
            request.form.get("type"), request.form.get("round"),
        )
        pool = filter_questions(QUESTIONS, args)

    random.shuffle(pool)
    picked = pool[:count]

    session["ids"] = [q["id"] for q in picked]
    session["idx"] = 0
    session["score"] = 0
    session["wrong_ids"] = []
    session["revealed"] = False
    session["selected"] = None
    return redirect(url_for("quiz"))


def _question_by_id(qid):
    for q in QUESTIONS:
        if q["id"] == qid:
            return q
    return None


@app.route("/quiz")
def quiz():
    ids = session.get("ids")
    if not ids:
        return redirect(url_for("setup"))

    idx = session.get("idx", 0)
    if idx >= len(ids):
        return redirect(url_for("summary"))

    q = _question_by_id(ids[idx])
    return render_template(
        "quiz.html", q=q, type_label=TYPE_LABEL.get(q["type"], q["type"]),
        idx=idx + 1, total=len(ids),
        revealed=session.get("revealed", False),
        selected=session.get("selected"),
        is_last=(idx + 1 == len(ids)),
    )


@app.route("/answer", methods=["POST"])
def answer():
    ids = session.get("ids")
    idx = session.get("idx", 0)
    if not ids or idx >= len(ids):
        return redirect(url_for("setup"))

    q = _question_by_id(ids[idx])
    selected = request.form.get("choice")
    session["selected"] = selected
    session["revealed"] = True
    if selected == q["answer"]:
        session["score"] = session.get("score", 0) + 1
    else:
        session["wrong_ids"] = session.get("wrong_ids", []) + [q["id"]]
    return redirect(url_for("quiz"))


@app.route("/next", methods=["POST"])
def next_question():
    session["idx"] = session.get("idx", 0) + 1
    session["revealed"] = False
    session["selected"] = None
    return redirect(url_for("quiz"))


@app.route("/summary")
def summary():
    ids = session.get("ids") or []
    score = session.get("score", 0)
    wrong_ids = session.get("wrong_ids", [])
    attempted = score + len(wrong_ids)
    wrong_qs = [_question_by_id(i) for i in wrong_ids]

    if attempted:
        existing = load_wrong_ids()
        existing.update(wrong_ids)
        correct_ids = [i for i in ids[:attempted] if i not in wrong_ids]
        existing.difference_update(correct_ids)
        save_wrong_ids(existing)

    pct = round(score / attempted * 100) if attempted else 0
    return render_template("summary.html", score=score, attempted=attempted, pct=pct, wrong_qs=wrong_qs)


if __name__ == "__main__":
    ip = _local_ip()
    print("=" * 60)
    print(f"  이 컴퓨터에서 확인:      http://127.0.0.1:5000")
    print(f"  휴대폰(같은 와이파이):   http://{ip}:5000")
    print("  (휴대폰 브라우저에 위 주소 입력 -> '홈 화면에 추가'하면 앱처럼 사용 가능)")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=False)
