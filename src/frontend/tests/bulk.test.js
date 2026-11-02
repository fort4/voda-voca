/*
 * 2026-11-02 - voda-voca - 일괄 등록 화면 로직과 단건 폼 로직 단위 테스트: 입력 파싱, 422 인덱스 매핑, 409 행 찾기, 변경분 계산, 목록 상태
 * 파일 위치: src/frontend/tests/bulk.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { findConflictRow, itemErrorsFromBody, parseBulkInput } from "../js/views/bulk-import.js";
import { diffWord } from "../js/views/word-form.js";
import { wordListState } from "../js/views/words.js";
import { validateWordExample, validateWordMeaning, validateWordTerm } from "../js/core/validate.js";

test("parseBulkInput: 빈 입력은 행이 없고 오류도 없다", () => {
  assert.deepEqual(parseBulkInput("   \n  "), { rows: [], headerSkipped: false, parseError: "" });
});

test("parseBulkInput: CSV 와 TSV 를 같은 행 구조로 읽는다", () => {
  const csv = parseBulkInput("term,meaning\napple,사과\n");
  assert.equal(csv.headerSkipped, true);
  assert.equal(csv.rows[0].term, "apple");

  const tsv = parseBulkInput("apple\t사과\tAn apple.\npear\t배\n", "words.tsv");
  assert.equal(tsv.rows.length, 2);
  assert.equal(tsv.rows[0].example, "An apple.");
  assert.equal(tsv.rows[1].example, "");
});

test("parseBulkInput: 깨진 UTF-8(U+FFFD)은 다시 저장하라는 안내로 바꾼다", () => {
  const result = parseBulkInput("apple,�");
  assert.equal(result.rows.length, 0);
  assert.match(result.parseError, /UTF-8/);
});

test("parseBulkInput: 따옴표 오류는 행 번호와 함께 알린다", () => {
  const result = parseBulkInput('apple,"사과\n');
  assert.match(result.parseError, /^1행:/);
});

test("itemErrorsFromBody: loc 의 items 인덱스를 꺼내고 요청 전체 오류는 null 로 둔다", () => {
  const body = {
    detail: [
      { loc: ["body", "items", 2, "meaning"], msg: "Value error, 뜻은 공백만으로 만들 수 없습니다." },
      { loc: ["body"], msg: "Value error, 요청 안에 같은 표제어가 있습니다: apple" },
    ],
  };
  assert.deepEqual(itemErrorsFromBody(body), [
    { index: 2, message: "뜻은 공백만으로 만들 수 없습니다." },
    { index: null, message: "요청 안에 같은 표제어가 있습니다: apple" },
  ]);
  assert.deepEqual(itemErrorsFromBody({ detail: "문자열" }), []);
});

test("findConflictRow: 요청 표기와 정확히 같은 첫 행을 찾는다", () => {
  const rows = [{ term: "kiwi" }, { term: "Apple" }, { term: "apple" }];
  assert.equal(findConflictRow(rows, "Apple"), 1);
  assert.equal(findConflictRow(rows, "APPLE"), -1, "서버가 보낸 표기 그대로 비교한다");
  assert.equal(findConflictRow(rows, null), -1);
});

test("diffWord: 바뀐 필드만 담고, 예문은 null 로 지울 수 있다", () => {
  const original = { term: "apple", meaning: "사과", example: "An apple." };
  assert.deepEqual(diffWord(original, { term: "apple", meaning: "사과", example: "An apple." }), {});
  assert.deepEqual(diffWord(original, { term: "apple", meaning: "사과 과일", example: "An apple." }), { meaning: "사과 과일" });
  assert.deepEqual(diffWord(original, { term: "apple", meaning: "사과", example: null }), { example: null });
  assert.deepEqual(diffWord({ term: "a", meaning: "b", example: null }, { term: "a", meaning: "b", example: null }), {});
});

test("wordListState: 로딩, 오류, 빈 목록, 검색 결과 없음, 성공을 구분한다", () => {
  assert.equal(wordListState({ status: "loading", items: [], total: 0, q: "" }), "loading");
  assert.equal(wordListState({ status: "error", items: [], total: 0, q: "" }), "error");
  assert.equal(wordListState({ status: "ok", items: [], total: 0, q: "" }), "empty");
  assert.equal(wordListState({ status: "ok", items: [], total: 0, q: "ap" }), "search-empty");
  assert.equal(wordListState({ status: "refreshing", items: [{ id: 1 }], total: 1, q: "a" }), "success");
});

test("단어 입력 검증: 표제어 100자, 뜻 200자, 예문 500자 경계", () => {
  assert.equal(validateWordTerm("a".repeat(100)), null);
  assert.match(validateWordTerm("a".repeat(101)), /100자/);
  assert.match(validateWordTerm("   "), /표제어를 입력/);
  assert.match(validateWordMeaning("가".repeat(201)), /200자/);
  assert.equal(validateWordExample(""), null);
  assert.match(validateWordExample("e".repeat(501)), /500자/);
});
