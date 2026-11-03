/*
 * 2026-11-02 - voda-voca - 학습 출처 해석 단위 테스트: 쿼리 파싱, API 파라미터, 4개 가드 경계 (REQ-014, REQ-019)
 * 파일 위치: src/frontend/tests/study-source.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { bookmarkListState } from "../js/views/bookmarks.js";
import {
  canStartQuiz,
  parseStudySource,
  sourceCountRequest,
  routeQueryFromSession,
  sourceFlashcardQuery,
  sourceQuizBody,
  sourceRouteQuery,
} from "../js/lib/study-source.js";

test("parseStudySource: 단어장 ID 또는 북마크 플래그를 읽고, 잘못된 값은 null", () => {
  assert.deepEqual(parseStudySource({ wordbook_id: "3" }), { kind: "wordbook", wordbookId: 3 });
  assert.deepEqual(parseStudySource({ bookmarks: "1" }), { kind: "bookmarks" });
  assert.deepEqual(parseStudySource({ bookmarked: "true" }), { kind: "bookmarks" });
  assert.equal(parseStudySource({}), null);
  assert.equal(parseStudySource({ wordbook_id: "abc" }), null);
  assert.equal(parseStudySource({ wordbook_id: "0" }), null);
});

test("API 파라미터는 출처에 따라 단어장 ID 또는 북마크 플래그를 쓴다", () => {
  const wb = { kind: "wordbook", wordbookId: 3 };
  const bm = { kind: "bookmarks" };
  assert.deepEqual(sourceFlashcardQuery(wb), { wordbook_id: 3 });
  assert.deepEqual(sourceFlashcardQuery(bm), { bookmarked: true });
  assert.deepEqual(sourceQuizBody(wb), { wordbook_id: 3 });
  assert.deepEqual(sourceQuizBody(bm), { bookmarks: true });
  assert.deepEqual(sourceRouteQuery(wb), { wordbook_id: "3" });
  assert.deepEqual(sourceRouteQuery(bm), { bookmarks: "1" });
});

test("sourceCountRequest: 단어 수는 size=1 로 세어 total 만 쓴다", () => {
  assert.deepEqual(sourceCountRequest({ kind: "wordbook", wordbookId: 9 }), {
    path: "/wordbooks/9/words",
    query: { page: 1, size: 1 },
  });
  assert.deepEqual(sourceCountRequest({ kind: "bookmarks" }), { path: "/bookmarks", query: { page: 1, size: 1 } });
});

test("canStartQuiz: 4개부터 시작할 수 있고 3개 이하는 막는다", () => {
  assert.equal(canStartQuiz(3), false);
  assert.equal(canStartQuiz(4), true);
  assert.equal(canStartQuiz(0), false);
});

test("북마크 화면 상태: 로딩, 오류, 빈 목록, 성공", () => {
  assert.equal(bookmarkListState({ status: "loading", items: [] }), "loading");
  assert.equal(bookmarkListState({ status: "error", items: [] }), "error");
  assert.equal(bookmarkListState({ status: "ok", items: [] }), "empty");
  assert.equal(bookmarkListState({ status: "ok", items: [{}] }), "success");
});

test("오답 복습 출처: 쿼리 wrong=1 을 읽고, 퀴즈 본문과 경로에 반영한다", () => {
  const source = parseStudySource({ wrong: "1" });
  assert.deepEqual(source, { kind: "wrong" });
  assert.deepEqual(sourceQuizBody(source), { wrong_only: true });
  assert.deepEqual(sourceRouteQuery(source), { wrong: "1" });
  assert.equal(parseStudySource({ wrong: "0" }), null);
});

test("routeQueryFromSession: 세션 출처로 '다시 풀기' 라우트 쿼리를 만든다", () => {
  assert.deepEqual(routeQueryFromSession({ source: "wordbook", wordbook_id: 7 }), { wordbook_id: "7" });
  assert.deepEqual(routeQueryFromSession({ source: "bookmarks", wordbook_id: null }), { bookmarks: "1" });
  assert.deepEqual(routeQueryFromSession({ source: "wrong", wordbook_id: null }), { wrong: "1" });
});
