# -*- coding: utf-8 -*-
"""복수정답(예: "①,③") 문항이 제대로 파싱되고 채점되는지 확인하는 자체 점검.

    python test_answers.py
"""
from extract_jsanhoe import _parse_answer_table
from web_app import is_correct

# 제126회 전산회계1급 확정답안 PDF에서 뽑은 실제 답안표 (8번·13번이 복수정답)
SAMPLE = (
    "A형\n<1>\n<2>\n<3>\n<4>\n<5>\n<6>\n<7>\n<8>\n<9> <10> <11> <12> <13> <14> <15>\n"
    "③\n①\n①\n①\n②\n①\n④\n①,③\n②\n④\n③\n②\n①,④\n④\n③\n"
)

table = _parse_answer_table(SAMPLE)
assert len(table) == 15, table
assert table[1] == "3"
assert table[8] == "1,3"
assert table[13] == "1,4"
assert table[15] == "3"

assert is_correct("3", "3")
assert not is_correct("2", "3")
assert is_correct("1", "1,3")
assert is_correct("3", "1,3")  # 복수정답은 둘 다 정답
assert not is_correct("2", "1,3")
assert not is_correct(None, "3")
assert not is_correct("3", None)

print("OK")
