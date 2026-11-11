/*
 * 2026-11-05 - voda-voca - 복습함 뷰모델 테스트: 북마크·오답 출처별 시작 가능 여부와 안내 문구, 북마크 항목 표시
 * 파일 위치: src/frontend/tests/review-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { REVIEW_MIN_WORDS, bookmarkRow, reviewSources } from "../js/core/review-model.js";

test("퀴즈 최소 단어 수(4)와 같은 기준을 쓴다", () => {
  assert.equal(REVIEW_MIN_WORDS, 4);
});

test("출처 두 개(북마크, 오답)를 이 순서로 돌려준다", () => {
  const sources = reviewSources({ bookmarkCount: 0, wrongCount: 0 });
  assert.deepEqual(sources.map((s) => s.id), ["bookmarks", "wrong"]);
});

test("4개 이상이면 시작할 수 있고 개수 문구를 준다", () => {
  const [bookmarks, wrong] = reviewSources({ bookmarkCount: 4, wrongCount: 12 });
  assert.equal(bookmarks.ready, true);
  assert.equal(bookmarks.message, "북마크한 단어 4개로 복습합니다.");
  assert.equal(wrong.ready, true);
  assert.equal(wrong.message, "틀린 단어 12개로 복습합니다.");
});

test("4개 미만이면 시작할 수 없고 부족한 이유를 현재 개수와 함께 밝힌다", () => {
  const [bookmarks, wrong] = reviewSources({ bookmarkCount: 3, wrongCount: 0 });
  assert.equal(bookmarks.ready, false);
  assert.equal(bookmarks.message, "북마크가 4개 이상이어야 복습할 수 있어요 (현재 3개).");
  assert.equal(wrong.ready, false);
  assert.equal(wrong.message, "틀린 단어가 4개 이상이어야 복습할 수 있어요 (현재 0개).");
});

test("개수를 모르면(null) 시작을 막되 숫자를 지어내지 않는다", () => {
  const [bookmarks] = reviewSources({ bookmarkCount: null, wrongCount: null });
  assert.equal(bookmarks.ready, false);
  assert.equal(bookmarks.count, null);
  assert.ok(!bookmarks.message.includes("null"));
});

test("북마크 행: 예문은 싣지 않고 품사·발음기호를 싣는다", () => {
  const row = bookmarkRow({ word_id: 7, vocabulary_title: "초급", term: "postpone", meaning: "연기하다", pos: "verb", phonetic: "poʊstˈpoʊn", example: "I postpone it.", example_meaning: "미룬다." });
  assert.equal(row.wordId, 7);
  assert.equal(row.term, "postpone");
  assert.equal(row.meaning, "연기하다");
  assert.equal(row.pos, "verb");
  assert.equal(row.phonetic, "poʊstˈpoʊn");
  assert.equal(row.source, "초급");
  assert.equal("example" in row, false);
  assert.equal("exampleMeaning" in row, false);
});

test("북마크 행: 품사·발음기호가 없으면 null 로 둔다", () => {
  const row = bookmarkRow({ word_id: 8, vocabulary_title: "초급", term: "a", meaning: "b" });
  assert.equal(row.pos, null);
  assert.equal(row.phonetic, null);
});
