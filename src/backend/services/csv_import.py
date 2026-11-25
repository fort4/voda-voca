# 2026-11-26 - voda-voca - CSV 일괄 등록의 파싱과 검증: 인코딩, 열 이름, 행 검사. DB 를 쓰지 않는다 (REQ-162)
# 파일 위치: src/backend/services/csv_import.py

import csv
import io
from dataclasses import dataclass

from pydantic import ValidationError

from backend.schemas.admin import WordInput

MAX_FILE_BYTES = 512 * 1024
MAX_ROWS = 500  # 열 이름 줄과 빈 줄은 세지 않는다
MAX_REPORTED_ERRORS = 20

REQUIRED_COLUMNS = ("term", "meaning")
COLUMNS = (*REQUIRED_COLUMNS, "example", "example_meaning")

_LABELS = {"term": "표제어", "meaning": "뜻", "example": "예문", "example_meaning": "예문 뜻"}
_EMPTY_MESSAGES = {"term": "표제어가 비어 있습니다.", "meaning": "뜻이 비어 있습니다."}
_SHOWN_NAME_MAX = 30  # 오류 문구에 옮겨 적는 열 이름 길이

ENCODING_MESSAGE = "UTF-8 파일이 아닙니다. 엑셀에서는 'CSV UTF-8(쉼표로 분리)' 형식으로 저장해 주세요."
HEADER_MESSAGE = f"첫 줄의 열 이름이 올바르지 않습니다. {','.join(COLUMNS)} 형식으로 작성해 주세요."
NO_ROWS_MESSAGE = "등록할 단어가 없는 파일입니다."
QUOTE_MESSAGE = "CSV 형식이 올바르지 않습니다. 큰따옴표의 짝을 확인해 주세요."


@dataclass(frozen=True)
class RowError:
    row: int  # 표 계산 프로그램에서 보이는 행 번호 (첫 줄이 1)
    message: str


class CsvImportError(Exception):
    """파일 전체를 거부한다. errors 는 행 단위 이유다 (파일 전체의 문제면 비어 있다)."""

    def __init__(self, message: str, errors: list[RowError] | None = None) -> None:
        super().__init__(message)
        self.errors = errors or []


def parse_words(data: bytes) -> list[WordInput]:
    """CSV 바이트를 단어 목록으로 바꾼다. 하나라도 틀리면 CsvImportError 다. 중복 표제어는 여기서 보지 않는다."""
    rows = _read_rows(_decode(data))
    if not rows:
        raise CsvImportError(NO_ROWS_MESSAGE)
    (header_row, header), body = rows[0], rows[1:]
    columns = _columns(header_row, header)
    if not body:
        raise CsvImportError(NO_ROWS_MESSAGE)
    if len(body) > MAX_ROWS:
        raise CsvImportError(f"한 번에 {MAX_ROWS}행까지 등록할 수 있습니다. 이 파일은 {len(body)}행입니다.")

    words: list[WordInput] = []
    errors: list[RowError] = []
    for number, cells in body:
        result = _word(columns, cells)
        if isinstance(result, str):
            errors.append(RowError(number, result))
        else:
            words.append(result)
    if errors:
        raise CsvImportError(
            f"오류가 있는 행이 {len(errors)}개라 파일 전체를 등록하지 않았습니다.", errors[:MAX_REPORTED_ERRORS]
        )
    return words


def _decode(data: bytes) -> str:
    try:
        text = data.decode("utf-8-sig")  # 엑셀이 붙이는 BOM 은 버린다
    except UnicodeDecodeError as exc:
        raise CsvImportError(ENCODING_MESSAGE) from exc
    if "\x00" in text:  # BOM 없는 UTF-16 은 UTF-8 로도 읽히지만 NUL 이 섞인다
        raise CsvImportError(ENCODING_MESSAGE)
    return text


def _read_rows(text: str) -> list[tuple[int, list[str]]]:
    """(행 번호, 칸 목록)을 돌려준다. 빈 줄은 버리되 행 번호에는 센다."""
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    rows: list[tuple[int, list[str]]] = []
    number = 0
    try:
        for number, cells in enumerate(reader, start=1):
            if any(cell.strip() for cell in cells):
                rows.append((number, cells))
    except csv.Error as exc:
        raise CsvImportError(QUOTE_MESSAGE, [RowError(number + 1, QUOTE_MESSAGE)]) from exc
    return rows


def _columns(row: int, header: list[str]) -> list[str]:
    names = [cell.strip().lower() for cell in header]
    problem = None
    for index, name in enumerate(names):
        if not name:
            problem = "이름이 없는 열이 있습니다."
        elif name not in COLUMNS:
            problem = f"알 수 없는 열입니다: {name[:_SHOWN_NAME_MAX]}"
        elif name in names[:index]:
            problem = f"같은 열이 두 번 있습니다: {name}"
        if problem:
            break
    missing = [name for name in REQUIRED_COLUMNS if name not in names]
    if missing:
        problem = f"필수 열이 없습니다: {', '.join(missing)}"
    if problem:
        raise CsvImportError(HEADER_MESSAGE, [RowError(row, problem)])
    return names


def _word(columns: list[str], cells: list[str]) -> WordInput | str:
    """한 행을 단어로 바꾼다. 틀리면 이유 문구를 돌려준다. 길이 규칙은 한 건 등록(WordInput)과 같다."""
    if any(cell.strip() for cell in cells[len(columns) :]):
        return "열보다 값이 많습니다. 쉼표가 들어간 값은 큰따옴표로 감싸 주세요."
    values = dict.fromkeys(COLUMNS, "") | dict(zip(columns, cells))
    try:
        return WordInput(**values)
    except ValidationError as exc:
        return " ".join(_describe(error) for error in exc.errors())


def _describe(error) -> str:  # noqa: ANN001 (pydantic ErrorDetails)
    name = str(error["loc"][0])
    if error["type"] == "string_too_short":
        return _EMPTY_MESSAGES[name]
    if error["type"] == "string_too_long":
        return f"{_LABELS[name]}: {error['ctx']['max_length']}자 이하여야 합니다."
    return f"{_LABELS[name]}: 값을 확인해 주세요."
