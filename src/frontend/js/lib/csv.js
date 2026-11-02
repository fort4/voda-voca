/*
 * 2026-11-02 - voda-voca - 일괄 등록 CSV·TSV 파서와 검증: 따옴표·CRLF·BOM 처리, 헤더 건너뜀, 100건 제한, 요청 내 중복 판정 (UI 설계서 §3.8)
 * 파일 위치: src/frontend/js/lib/csv.js
 */

import { LIMITS } from "../core/validate.js";

export const BULK_MAX_ITEMS = 100;
const HEADER_TERMS = ["표제어", "term"];
const HEADER_MEANINGS = ["뜻", "meaning"];

export class CsvParseError extends Error {
  /** @param {string} message @param {number} lineNo */
  constructor(message, lineNo) {
    super(message);
    this.name = "CsvParseError";
    this.lineNo = lineNo;
  }
}

/** @param {string} text @returns {string} BOM(U+FEFF)을 걷어낸 문자열 */
export function stripBom(text) {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * 구분자를 정한다. .tsv 파일이거나 첫 비어 있지 않은 줄에 탭이 있으면 탭, 아니면 쉼표.
 * @param {string} text
 * @param {string} [fileName]
 * @returns {"," | "\t"}
 */
export function detectDelimiter(text, fileName = "") {
  if (fileName.toLowerCase().endsWith(".tsv")) return "\t";
  const firstLine = stripBom(text).split(/\r?\n/).find((line) => line.trim() !== "") ?? "";
  return firstLine.includes("\t") ? "\t" : ",";
}

/**
 * RFC 4180 에 가까운 파서. 큰따옴표로 감싼 필드(안의 구분자, 줄바꿈 포함), "" 이스케이프, CRLF/LF 를 처리한다.
 * 완전히 빈 줄은 버린다. 닫히지 않은 따옴표는 CsvParseError 를 던진다.
 * @param {string} input
 * @param {"," | "\t"} [delimiter]
 * @returns {Array<{lineNo: number, cells: string[]}>}
 */
export function parseDelimited(input, delimiter = ",") {
  const text = stripBom(input);
  const records = [];
  let cells = [];
  let field = "";
  let inQuotes = false;
  let line = 1;
  let recordLine = 1;

  const endRecord = () => {
    cells.push(field);
    if (cells.some((cell) => cell.trim() !== "")) records.push({ lineNo: recordLine, cells });
    cells = [];
    field = "";
    recordLine = line;
  };

  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          inQuotes = false;
        }
      } else {
        if (ch === "\n") line += 1;
        field += ch;
      }
      continue;
    }
    if (ch === '"' && field === "") {
      inQuotes = true;
    } else if (ch === delimiter) {
      cells.push(field);
      field = "";
    } else if (ch === "\r") {
      // CRLF 의 CR 은 무시한다. LF 가 줄 끝이다.
    } else if (ch === "\n") {
      line += 1; // 줄을 먼저 넘긴 뒤 레코드를 끝내야 다음 레코드의 시작 줄이 맞는다
      endRecord();
    } else {
      field += ch;
    }
  }
  if (inQuotes) throw new CsvParseError("닫히지 않은 큰따옴표가 있습니다.", recordLine);
  if (cells.length > 0 || field !== "") endRecord();
  return records;
}

/** @param {string} cell @returns {string} */
function normalizeHeaderCell(cell) {
  return cell.trim().toLowerCase();
}

/**
 * 파싱된 레코드를 단어 후보 행으로 바꾼다. 첫 레코드가 헤더(표제어,뜻 / term,meaning)이면 건너뛴다.
 * @param {Array<{lineNo: number, cells: string[]}>} records
 * @returns {{headerSkipped: boolean, rows: Array<{lineNo: number, term: string, meaning: string, example: string, extraColumns: boolean, errors: string[]}>}}
 */
export function toCandidateRows(records) {
  let headerSkipped = false;
  let start = 0;
  if (records.length > 0) {
    const [first] = records;
    const term = normalizeHeaderCell(first.cells[0] ?? "");
    const meaning = normalizeHeaderCell(first.cells[1] ?? "");
    if (HEADER_TERMS.includes(term) && HEADER_MEANINGS.includes(meaning)) {
      headerSkipped = true;
      start = 1;
    }
  }
  const rows = records.slice(start).map(({ lineNo, cells }) => ({
    lineNo,
    term: (cells[0] ?? "").trim(),
    meaning: (cells[1] ?? "").trim(),
    example: (cells[2] ?? "").trim(),
    extraColumns: cells.slice(3).some((cell) => cell.trim() !== ""),
    errors: [],
  }));
  return { headerSkipped, rows };
}

/**
 * 요청 안 중복 판정용 키. 대소문자와 악센트를 무시한다 (Apple = apple, café = cafe).
 * 서버의 term_key 와 취지가 같지만 완전히 같은 알고리즘은 아니다. 최종 판정은 서버가 한다.
 * @param {string} term
 * @returns {string}
 */
export function termKey(term) {
  return term.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase();
}

/**
 * 행마다 오류를 채운다. 빈 값, 글자 수, 열 개수, 요청 안 중복을 검사한다. 입력 배열을 바꾸지 않고 새 배열을 돌려준다.
 * 중복은 처음 나온 행을 기준으로 뒤에 나온 행에 "N행과 같은 표제어" 오류를 붙인다.
 * @param {Array<{lineNo: number, term: string, meaning: string, example: string, errors: string[], extraColumns?: boolean}>} rows
 */
export function validateCandidateRows(rows) {
  const firstLineByKey = new Map();
  return rows.map((row) => {
    const errors = [];
    if (row.extraColumns) errors.push("열이 세 개를 넘습니다. 쉼표나 탭을 확인해 주세요.");
    if (!row.term) errors.push("표제어가 비어 있습니다.");
    if (!row.meaning) errors.push("뜻이 비어 있습니다.");
    if (row.term.length > LIMITS.WORD_TERM_MAX) errors.push(`표제어는 ${LIMITS.WORD_TERM_MAX}자 이하여야 합니다.`);
    if (row.meaning.length > LIMITS.WORD_MEANING_MAX) errors.push(`뜻은 ${LIMITS.WORD_MEANING_MAX}자 이하여야 합니다.`);
    if (row.example.length > LIMITS.WORD_EXAMPLE_MAX) errors.push(`예문은 ${LIMITS.WORD_EXAMPLE_MAX}자 이하여야 합니다.`);
    if (row.term) {
      const key = termKey(row.term);
      const first = firstLineByKey.get(key);
      if (first === undefined) {
        firstLineByKey.set(key, row.lineNo);
      } else {
        errors.push(`${first}행과 같은 표제어입니다.`);
      }
    }
    return { ...row, errors };
  });
}

/**
 * 서버 전송용 WordBulkCreate 본문을 만든다. 오류가 없는 행만 입력 순서대로 담는다.
 * 행 번호와 구분자 정보는 넣지 않는다.
 * @param {Array<{term: string, meaning: string, example: string, errors: string[]}>} rows
 * @returns {{items: Array<{term: string, meaning: string, example: string|null}>}}
 */
export function buildBulkPayload(rows) {
  return {
    items: rows
      .filter((row) => row.errors.length === 0)
      .map((row) => ({ term: row.term, meaning: row.meaning, example: row.example || null })),
  };
}

/**
 * 100건을 넘는지 확인한다. 넘으면 전송을 막는다.
 * @param {number} count
 * @returns {boolean}
 */
export function exceedsBulkLimit(count) {
  return count > BULK_MAX_ITEMS;
}
