/*
 * 2026-11-02 - voda-voca - CSV·TSV 파서와 일괄 등록 검증 단위 테스트: 따옴표, CRLF, BOM, 헤더, 중복(대소문자·악센트), 100건 제한
 * 파일 위치: src/frontend/tests/csv.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import {
  BULK_MAX_ITEMS,
  buildBulkPayload,
  CsvParseError,
  detectDelimiter,
  exceedsBulkLimit,
  parseDelimited,
  stripBom,
  termKey,
  toCandidateRows,
  validateCandidateRows,
} from "../js/lib/csv.js";

test("stripBom 은 맨 앞의 BOM 만 걷어낸다", () => {
  assert.equal(stripBom("﻿apple"), "apple");
  assert.equal(stripBom("apple﻿"), "apple﻿");
});

test("detectDelimiter: .tsv 파일이거나 첫 줄에 탭이 있으면 탭, 그 밖은 쉼표", () => {
  assert.equal(detectDelimiter("a\tb", "words.tsv"), "\t");
  assert.equal(detectDelimiter("a,b", "words.TSV"), "\t");
  assert.equal(detectDelimiter("\n\napple\tsa", ""), "\t", "빈 줄을 건너뛰고 첫 내용 줄을 본다");
  assert.equal(detectDelimiter("apple,사과", "words.csv"), ",");
});

test("parseDelimited: 기본 CSV 와 CRLF 를 처리한다", () => {
  const records = parseDelimited("apple,사과\r\npear,배\r\n");
  assert.deepEqual(records.map((r) => r.cells), [["apple", "사과"], ["pear", "배"]]);
  assert.deepEqual(records.map((r) => r.lineNo), [1, 2]);
});

test(`parseDelimited: 따옴표 안의 쉼표, "" 이스케이프, 줄바꿈을 한 필드로 본다`, () => {
  const records = parseDelimited('apple,"사과, 과일","그는 ""사과""라고 했다.\n두 번째 줄"\n');
  assert.deepEqual(records[0].cells, ["apple", "사과, 과일", '그는 "사과"라고 했다.\n두 번째 줄']);
});

test("parseDelimited: 빈 줄은 버리고 BOM 을 무시한다", () => {
  const records = parseDelimited("﻿apple,사과\n\n   \npear,배\n");
  assert.deepEqual(records.map((r) => r.cells[0]), ["apple", "pear"]);
  assert.deepEqual(records.map((r) => r.lineNo), [1, 4]);
});

test("parseDelimited: TSV 는 탭으로 나누고 따옴표 규칙을 따른다", () => {
  const records = parseDelimited('apple\t사과\t"예문, 쉼표"\n', "\t");
  assert.deepEqual(records[0].cells, ["apple", "사과", "예문, 쉼표"]);
});

test("parseDelimited: 닫히지 않은 따옴표는 CsvParseError 를 던진다", () => {
  assert.throws(
    () => parseDelimited('apple,"사과\npear,배\n'),
    (error) => error instanceof CsvParseError && error.name === "CsvParseError",
  );
});

test("toCandidateRows: 첫 줄이 표제어,뜻 헤더이면 건너뛴다 (대소문자 무시)", () => {
  const withHeader = toCandidateRows(parseDelimited("Term,Meaning\napple,사과\n"));
  assert.equal(withHeader.headerSkipped, true);
  assert.equal(withHeader.rows.length, 1);
  assert.equal(withHeader.rows[0].term, "apple");

  const noHeader = toCandidateRows(parseDelimited("apple,사과\n"));
  assert.equal(noHeader.headerSkipped, false);
  assert.equal(noHeader.rows.length, 1);
});

test("toCandidateRows: 세 번째 칸 뒤에 값이 있으면 열 초과로 표시한다", () => {
  const { rows } = toCandidateRows(parseDelimited("apple,사과,예문,잘못\npear,배\n"));
  assert.equal(rows[0].extraColumns, true);
  assert.equal(rows[1].extraColumns, false);
});

test("termKey: 대소문자와 악센트를 무시한다", () => {
  assert.equal(termKey("Apple"), termKey("apple"));
  assert.equal(termKey("café"), termKey("CAFE"));
  assert.notEqual(termKey("apple"), termKey("apples"));
});

test("validateCandidateRows: 빈 값, 글자 수, 열 초과를 행 오류로 붙인다", () => {
  const rows = validateCandidateRows([
    { lineNo: 1, term: "", meaning: "뜻", example: "", extraColumns: false, errors: [] },
    { lineNo: 2, term: "a".repeat(101), meaning: "", example: "", extraColumns: true, errors: [] },
    { lineNo: 3, term: "ok", meaning: "b".repeat(201), example: "e".repeat(501), extraColumns: false, errors: [] },
  ]);
  assert.match(rows[0].errors.join(" "), /표제어가 비어/);
  assert.match(rows[1].errors.join(" "), /100자/);
  assert.match(rows[1].errors.join(" "), /뜻이 비어/);
  assert.match(rows[1].errors.join(" "), /열이 세 개/);
  assert.match(rows[2].errors.join(" "), /뜻은 200자/);
  assert.match(rows[2].errors.join(" "), /예문은 500자/);
});

test("validateCandidateRows: 요청 안 중복은 뒤에 나온 행에 처음 행 번호와 함께 표시한다", () => {
  const rows = validateCandidateRows([
    { lineNo: 1, term: "Apple", meaning: "사과", example: "", extraColumns: false, errors: [] },
    { lineNo: 2, term: "pear", meaning: "배", example: "", extraColumns: false, errors: [] },
    { lineNo: 3, term: "apple", meaning: "사과2", example: "", extraColumns: false, errors: [] },
    { lineNo: 4, term: "café", meaning: "커피", example: "", extraColumns: false, errors: [] },
    { lineNo: 5, term: "CAFE", meaning: "커피2", example: "", extraColumns: false, errors: [] },
  ]);
  assert.deepEqual(rows[0].errors, []);
  assert.deepEqual(rows[1].errors, []);
  assert.deepEqual(rows[2].errors, ["1행과 같은 표제어입니다."]);
  assert.deepEqual(rows[4].errors, ["4행과 같은 표제어입니다."]);
});

test("buildBulkPayload: 오류 없는 행만 입력 순서대로, 빈 예문은 null 로 담는다", () => {
  const payload = buildBulkPayload([
    { lineNo: 1, term: "apple", meaning: "사과", example: "", errors: [] },
    { lineNo: 2, term: "", meaning: "배", example: "", errors: ["표제어가 비어 있습니다."] },
    { lineNo: 3, term: "pear", meaning: "배", example: "맛있다", errors: [] },
  ]);
  assert.deepEqual(payload, {
    items: [
      { term: "apple", meaning: "사과", example: null },
      { term: "pear", meaning: "배", example: "맛있다" },
    ],
  });
  assert.deepEqual(Object.keys(payload), ["items"], "행 번호 같은 입력 정보는 보내지 않는다");
});

test("exceedsBulkLimit: 100건까지는 허용하고 101건부터 막는다", () => {
  assert.equal(BULK_MAX_ITEMS, 100);
  assert.equal(exceedsBulkLimit(100), false);
  assert.equal(exceedsBulkLimit(101), true);
});
