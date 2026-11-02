/*
 * 2026-11-02 - voda-voca - 단어장 목록 상태 계산 단위 테스트: Loading/Empty/Error/Success 분기와 더 보기 조건
 * 파일 위치: src/frontend/tests/wordbooks.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { hasMore, listViewState, wordCountLabel } from "../js/views/wordbooks.js";

test("listViewState: 로딩, 오류, 빈 목록, 성공을 구분한다", () => {
  assert.equal(listViewState({ status: "loading", items: [], total: 0 }), "loading");
  assert.equal(listViewState({ status: "error", items: [], total: 0 }), "error");
  assert.equal(listViewState({ status: "ok", items: [], total: 0 }), "empty");
  assert.equal(listViewState({ status: "ok", items: [{ id: 1 }], total: 1 }), "success");
});

test("hasMore: 받은 개수가 전체보다 적을 때만 더 보기를 보인다", () => {
  assert.equal(hasMore({ items: new Array(20), total: 45 }), true);
  assert.equal(hasMore({ items: new Array(45), total: 45 }), false);
});

test("wordCountLabel: 단어 수를 천 단위 구분 기호와 함께 보여 주고, 0 과 잘못된 값은 0개", () => {
  assert.equal(wordCountLabel(0), "0개 단어");
  assert.equal(wordCountLabel(200), "200개 단어");
  assert.equal(wordCountLabel(1000), "1,000개 단어");
  assert.equal(wordCountLabel(undefined), "0개 단어");
  assert.equal(wordCountLabel(-3), "0개 단어");
});
