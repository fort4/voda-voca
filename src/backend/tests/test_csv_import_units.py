# 2026-11-26 - voda-voca - CSV 파싱 단위 테스트: 인코딩, 열 이름, 빈 줄, 행 오류 보고, 행 수 상한 (REQ-162)
# 파일 위치: src/backend/tests/test_csv_import_units.py

import pytest

from backend.services.csv_import import MAX_REPORTED_ERRORS, MAX_ROWS, CsvImportError, parse_words

pytestmark = pytest.mark.no_db

HEADER = "term,meaning,example,example_meaning\n"


def parse(text: str) -> list[tuple]:
    return [(w.term, w.meaning, w.example, w.example_meaning) for w in parse_words(text.encode("utf-8"))]


def failure(data: str | bytes) -> CsvImportError:
    with pytest.raises(CsvImportError) as caught:
        parse_words(data.encode("utf-8") if isinstance(data, str) else data)
    return caught.value


def rows_of(error: CsvImportError) -> list[int]:
    return [e.row for e in error.errors]


def test_reads_all_columns_and_trims_spaces() -> None:
    assert parse(HEADER + " ladle , 국자 , Use a ladle. , 국자를 써. \n") == [
        ("ladle", "국자", "Use a ladle.", "국자를 써.")
    ]


def test_accepts_a_bom_and_windows_line_endings() -> None:
    data = "﻿term,meaning\r\nladle,국자\r\n".encode("utf-8")

    assert [(w.term, w.meaning) for w in parse_words(data)] == [("ladle", "국자")]


def test_columns_may_come_in_any_order_and_optional_ones_may_be_absent() -> None:
    assert parse("meaning,term\n국자,ladle\n") == [("ladle", "국자", None, None)]


def test_header_names_ignore_case_and_spaces() -> None:
    assert parse("Term, MEANING \nladle,국자\n") == [("ladle", "국자", None, None)]


def test_quoted_values_keep_commas_quotes_and_line_breaks() -> None:
    text = HEADER + 'abdicate,"퇴위하다, 포기하다","He said ""no"".\nThen left.",\n'

    assert parse(text) == [("abdicate", "퇴위하다, 포기하다", 'He said "no".\nThen left.', None)]


def test_without_an_example_the_translation_is_dropped() -> None:
    assert parse(HEADER + "ladle,국자,,남으면 안 됨\n") == [("ladle", "국자", None, None)]


def test_blank_lines_are_ignored_even_before_the_header() -> None:
    assert parse("\n,,,\n" + HEADER + "\nladle,국자,,\n,,,\n   ,  \nfork,포크\n\n") == [
        ("ladle", "국자", None, None),
        ("fork", "포크", None, None),
    ]


def test_trailing_empty_cells_are_allowed() -> None:
    assert parse("term,meaning\nladle,국자,,,\n") == [("ladle", "국자", None, None)]


def test_duplicate_terms_are_not_a_parse_error() -> None:
    assert len(parse("term,meaning\nladle,국자\nLadle,국자\n")) == 2


@pytest.mark.parametrize("data", ["", "\n\n", "term,meaning\n", "term,meaning\n,\n"])
def test_a_file_without_rows_is_rejected(data: str) -> None:
    assert "없" in str(failure(data))


@pytest.mark.parametrize(
    "data",
    [
        "term,meaning\nladle,국자\n".encode("cp949"),
        "term,meaning\nladle,국자\n".encode("utf-16"),
        "term,meaning\nladle,x\n".encode("utf-16-le"),  # BOM 이 없으면 UTF-8 로 읽히지만 NUL 이 섞인다
    ],
)
def test_other_encodings_are_rejected_with_a_hint(data: bytes) -> None:
    assert "CSV UTF-8" in str(failure(data))


@pytest.mark.parametrize(
    ("header", "hint"),
    [
        ("term", "meaning"),
        ("meaning,example", "term"),
        ("ladle,국자", "term"),  # 열 이름 줄이 없다
        ("term,meaning,pos", "pos"),
        ("term,meaning,term", "term"),
        ("term,meaning,", "이름"),
    ],
)
def test_a_wrong_header_is_reported_on_its_row(header: str, hint: str) -> None:
    error = failure(f"{header}\nladle,국자\n")

    assert rows_of(error) == [1]
    assert hint in error.errors[0].message


def test_a_long_unknown_column_name_is_shortened() -> None:
    error = failure("term,meaning," + "z" * 5000 + "\na,b,c\n")

    assert len(error.errors[0].message) < 200


def test_row_errors_use_spreadsheet_row_numbers_and_name_every_problem() -> None:
    text = HEADER + "ladle,국자,,\n\n,뜻만,,\n" + "t" * 101 + ",,,\nfork,포크,,\n"

    error = failure(text)

    assert rows_of(error) == [4, 5]
    assert "표제어" in error.errors[0].message
    assert "표제어" in error.errors[1].message and "100자" in error.errors[1].message
    assert "뜻" in error.errors[1].message


@pytest.mark.parametrize(
    ("row", "label", "limit"),
    [
        ("a," + "m" * 201 + ",,", "뜻", "200자"),
        ("a,b," + "e" * 501 + ",", "예문", "500자"),
        ("a,b,c," + "e" * 501, "예문 뜻", "500자"),
    ],
)
def test_length_limits_match_the_single_word_form(row: str, label: str, limit: str) -> None:
    message = failure(HEADER + row + "\n").errors[0].message

    assert label in message and limit in message


def test_values_at_the_length_limit_are_accepted() -> None:
    row = ",".join(["t" * 100, "m" * 200, "e" * 500, "k" * 500])

    assert len(parse(HEADER + row + "\n")) == 1


def test_an_unquoted_comma_is_reported_with_a_hint() -> None:
    error = failure("term,meaning\nabdicate,퇴위하다, 포기하다\n")

    assert rows_of(error) == [2]
    assert "큰따옴표" in error.errors[0].message


@pytest.mark.parametrize("row", ['ladle,"국자\n', 'ladle,"국"자\n'])
def test_broken_quoting_is_reported_with_the_row(row: str) -> None:
    error = failure("term,meaning\nfork,포크\n" + row)

    assert rows_of(error) == [3]
    assert "큰따옴표" in error.errors[0].message


def test_only_the_first_errors_are_listed_but_all_are_counted() -> None:
    error = failure("term,meaning\n" + ",뜻\n" * (MAX_REPORTED_ERRORS + 5))

    assert MAX_REPORTED_ERRORS == 20
    assert rows_of(error) == list(range(2, 22))
    assert "25" in str(error)


def test_the_row_limit_counts_data_rows_only() -> None:
    body = "".join(f"w{i},뜻\n" for i in range(MAX_ROWS))

    assert MAX_ROWS == 3000  # 과제 제공 파일(2,000개)을 한 번에 올릴 수 있어야 한다 (VOCA-FR-003)
    assert len(parse("term,meaning\n\n" + body + "\n")) == 3000
    message = str(failure("term,meaning\n" + body + "extra,뜻\n"))
    assert "3000" in message and "3001" in message


# ---------- 한글 열 이름 (과제 제공 파일, #40) ----------


def test_the_course_header_is_accepted_with_a_bom() -> None:
    assert parse("\ufeff영단어,뜻\r\napple,사과\r\n") == [("apple", "사과", None, None)]


@pytest.mark.parametrize("header", ["영단어,뜻,예문,예문 뜻", "영단어, 뜻 ,예문,예문뜻", "영단어,meaning,example,예문 뜻"])
def test_korean_names_work_for_every_column_and_may_be_mixed(header: str) -> None:
    assert parse(f"{header}\nladle,국자,Use a ladle.,국자를 써.\n") == [("ladle", "국자", "Use a ladle.", "국자를 써.")]


@pytest.mark.parametrize(
    ("header", "hint"),
    [("영단어,뜻,term", "term"), ("영단어,예문", "meaning"), ("단어,뜻", "단어")],
)
def test_wrong_korean_headers_are_rejected(header: str, hint: str) -> None:
    error = failure(f"{header}\nladle,국자,x\n")

    assert rows_of(error) == [1]
    assert hint in error.errors[0].message


def test_the_header_hint_names_both_formats() -> None:
    message = str(failure("a,b\nladle,국자\n"))

    assert "영단어,뜻" in message and "term,meaning" in message
