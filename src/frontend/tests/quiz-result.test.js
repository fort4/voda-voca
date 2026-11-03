/*
 * 2026-11-03 - voda-voca - 퀴즈 결과 문구 단위 테스트: 일부만 푼 결과와 전부 푼 결과를 구분해 설명한다 (이슈 #8)
 * 파일 위치: src/frontend/tests/quiz-result.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { describeResult, retryGuidance } from "../js/core/quiz-result.js";

test("전부 풀면 점수와 정답률만 보여 준다", () => {
  const d = describeResult({ total: 10, answered: 10, correct_count: 7, accuracy: 70 });
  assert.equal(d.score, "7 / 10");
  assert.equal(d.accuracyLabel, "정답률 70%");
  assert.equal(d.note, "");
  assert.equal(d.perfect, false);
});

test("모두 맞히면 perfect", () => {
  assert.equal(describeResult({ total: 5, answered: 5, correct_count: 5, accuracy: 100 }).perfect, true);
});

test("일부만 풀면 푼 문항 기준임을 밝힌다", () => {
  const d = describeResult({ total: 10, answered: 4, correct_count: 3, accuracy: 75 });
  assert.equal(d.score, "3 / 4");
  assert.equal(d.accuracyLabel, "정답률 75%");
  assert.match(d.note, /10문항 중 4문항/);
  assert.equal(d.perfect, false, "일부만 풀고 다 맞힌 것은 모두 맞힌 것이 아니다");
});

test("하나도 풀지 않았으면 정답률 대신 안내한다", () => {
  const d = describeResult({ total: 10, answered: 0, correct_count: 0, accuracy: 0 });
  assert.equal(d.score, "0 / 0");
  assert.equal(d.accuracyLabel, "푼 문항이 없습니다");
  assert.match(d.note, /10문항 중 0문항/);
});

test("retryGuidance: 일부만 푼 퀴즈는 이어 풀 수 없음을 알리고 새로 시작하도록 안내한다", () => {
  assert.match(retryGuidance({ total: 10, answered: 4 }), /새 퀴즈/);
  assert.equal(retryGuidance({ total: 10, answered: 10 }), "");
});
