/*
 * 2026-11-02 - voda-voca - 결과 캐시 단위 테스트: 저장·복구, 깨진 값, 저장소 오류, 로그아웃 시 정리 (확정 결정 2)
 * 파일 위치: src/frontend/tests/result-cache.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { clearQuizResults, loadQuizResult, resultKey, saveQuizResult } from "../js/core/result-cache.js";

/** sessionStorage 와 같은 인터페이스의 가짜 저장소. throwOnSet 이면 저장이 실패한다. */
class FakeStorage {
  constructor({ throwOnSet = false } = {}) {
    this.map = new Map();
    this.throwOnSet = throwOnSet;
  }
  get length() { return this.map.size; }
  key(i) { return [...this.map.keys()][i] ?? null; }
  getItem(k) { return this.map.has(k) ? this.map.get(k) : null; }
  setItem(k, v) {
    if (this.throwOnSet) throw new Error("QuotaExceededError");
    this.map.set(k, String(v));
  }
  removeItem(k) { this.map.delete(k); }
}

const RECORD = { sessionId: 7, total: 3, correct_count: 2, accuracy: 66.7, items: [{ question_id: 0, is_correct: true }] };

test("resultKey 는 세션 ID 로 키를 만든다", () => {
  assert.equal(resultKey(7), "voda.quizResult.7");
});

test("저장한 결과를 같은 세션 ID 로 다시 읽는다 (새로고침 복구)", () => {
  const storage = new FakeStorage();
  assert.equal(saveQuizResult(storage, 7, RECORD), true);
  const loaded = loadQuizResult(storage, 7);
  assert.equal(loaded.correct_count, 2);
  assert.equal(loaded.items.length, 1);
  assert.ok(typeof loaded.savedAt === "string");
  assert.equal(loadQuizResult(storage, 8), null, "다른 세션 ID 는 읽히지 않는다");
});

test("깨진 JSON 이나 모양이 다른 값은 null 로 본다", () => {
  const storage = new FakeStorage();
  storage.setItem("voda.quizResult.1", "{broken");
  assert.equal(loadQuizResult(storage, 1), null);
  storage.setItem("voda.quizResult.2", JSON.stringify({ total: 3 }));
  assert.equal(loadQuizResult(storage, 2), null, "items 배열이 없으면 결과가 아니다");
});

test("저장소가 실패해도 예외 없이 false 를 돌려준다", () => {
  const storage = new FakeStorage({ throwOnSet: true });
  assert.equal(saveQuizResult(storage, 7, RECORD), false);
});

test("저장소가 없으면(null) 저장과 읽기 모두 안전하게 끝난다", () => {
  assert.equal(saveQuizResult(null, 7, RECORD), false);
  assert.equal(loadQuizResult(undefined, 7), null);
  assert.equal(clearQuizResults(null), 0);
});

test("clearQuizResults 는 이 앱의 결과 키만 지우고 나머지는 남긴다", () => {
  const storage = new FakeStorage();
  saveQuizResult(storage, 1, RECORD);
  saveQuizResult(storage, 2, RECORD);
  storage.setItem("other.key", "keep");
  assert.equal(clearQuizResults(storage), 2);
  assert.equal(storage.getItem("other.key"), "keep");
  assert.equal(loadQuizResult(storage, 1), null);
});
