# 2026-11-02 - voda-voca - 기본 단어장 시드 데이터 검증: 각 200제, 중복 없음, 필드 제한, 예문에 표제어 포함 (DB 없이 실행)
# 파일 위치: src/backend/tests/test_seed_data.py

from backend.services.seed import DEFAULT_WORDBOOKS, PRESET_WORDBOOKS, SEED_DIR, default_wordbooks, load_preset
from backend.schemas.word import TERM_MAX_CHARS, MEANING_MAX_CHARS, EXAMPLE_MAX_CHARS, EXAMPLE_MEANING_MAX_CHARS
from backend.tests.helpers import DEFAULT_WORDBOOK_NAMES


def test_three_default_wordbooks_with_expected_names() -> None:
    books = default_wordbooks()
    assert [b.name for b in books] == list(DEFAULT_WORDBOOK_NAMES)
    assert [b.name for b in books] == [name for _, name in DEFAULT_WORDBOOKS]


def test_each_seed_file_has_exactly_200_words() -> None:
    for book in default_wordbooks():
        assert len(book.words) == 200, book.name


def test_seed_files_exist_in_the_expected_directory() -> None:
    for file_name, _ in DEFAULT_WORDBOOKS:
        assert (SEED_DIR / file_name).is_file(), file_name


def test_terms_are_unique_per_wordbook_ignoring_case() -> None:
    """같은 단어장 안 표제어는 DB 콜레이션상 대소문자 무시로 유일해야 한다 (uk_words_wordbook_term)."""
    for book in default_wordbooks():
        terms = [w.term.lower() for w in book.words]
        assert len(set(terms)) == len(terms), book.name


def test_every_field_is_present_and_within_the_word_limits() -> None:
    for book in default_wordbooks():
        for w in book.words:
            assert w.term.strip() == w.term and w.term, w
            assert w.meaning.strip() == w.meaning and w.meaning, w
            assert w.example.strip() == w.example and w.example, w
            assert len(w.term) <= TERM_MAX_CHARS, w
            assert len(w.meaning) <= MEANING_MAX_CHARS, w
            assert len(w.example) <= EXAMPLE_MAX_CHARS, w


def test_example_sentence_contains_its_term_for_quiz_explanations() -> None:
    """해설에 쓰는 예문에는 표제어가 들어 있어야 학습자가 어떤 형태로 쓰였는지 알 수 있다."""
    for book in default_wordbooks():
        missing = [w.term for w in book.words if w.term.lower() not in w.example.lower()]
        assert missing == [], book.name


def test_intermediate_1000_preset_file_has_1000_valid_words() -> None:
    """추천 1,000제 CSV 가 실제로 들어 있으면 개수, 중복, 필드, 예문 조건을 모두 만족해야 한다."""
    file_name, _ = PRESET_WORDBOOKS["intermediate-1000"]
    assert (SEED_DIR / file_name).is_file(), file_name
    _, words = load_preset("intermediate-1000")
    assert len(words) == 1000
    terms = [w.term.lower() for w in words]
    assert len(set(terms)) == len(terms)
    for w in words:
        assert w.term and w.meaning and w.example, w
        assert len(w.term) <= TERM_MAX_CHARS, w
        assert len(w.meaning) <= MEANING_MAX_CHARS, w
        assert len(w.example) <= EXAMPLE_MAX_CHARS, w
        assert w.term.lower() in w.example.lower(), w


def test_loader_is_cached_so_the_files_are_read_once() -> None:
    assert default_wordbooks() is default_wordbooks()


def test_every_seed_word_has_a_translation_within_the_limit() -> None:
    """예문이 있는 모든 시드 단어는 예문 뜻을 가진다. 길이는 DB 컬럼(500자)을 넘지 않는다."""
    words = [w for book in default_wordbooks() for w in book.words]
    _, preset = load_preset("intermediate-1000")
    for w in [*words, *preset]:
        assert w.example, w
        assert isinstance(w.example_meaning, str) and w.example_meaning.strip() == w.example_meaning, w
        assert 0 < len(w.example_meaning) <= EXAMPLE_MEANING_MAX_CHARS, w
        assert w.example_meaning != w.example, w


def test_json_seed_files_declare_example_meaning_for_every_item() -> None:
    import json

    for file_name, _ in DEFAULT_WORDBOOKS:
        raw = json.loads((SEED_DIR / file_name).read_text(encoding="utf-8"))
        assert all(isinstance(item.get("example_meaning"), str) for item in raw), file_name


def test_intermediate_csv_header_is_the_four_column_form() -> None:
    import csv

    with (SEED_DIR / PRESET_WORDBOOKS["intermediate-1000"][0]).open(encoding="utf-8-sig", newline="") as fh:
        assert next(csv.reader(fh)) == ["term", "meaning", "example", "example_meaning"]
