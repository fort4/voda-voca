/*
 * 2026-11-02 - voda-voca - 학습 이력 집계와 한국 날짜 묶음 단위 테스트, 시각 표시 (REQ-016)
 * 파일 위치: src/frontend/tests/study-stats.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { kstDateKey, kstTime } from "../js/core/format.js";
import { groupByKstDate, summarizeLogs, uniqueWrongWordIds } from "../js/lib/study-stats.js";

test("summarizeLogs: 정답 수, 오답 수, 정답률(소수 첫째 자리)을 계산한다", () => {
  const logs = [{ is_correct: true }, { is_correct: false }, { is_correct: true }];
  assert.deepEqual(summarizeLogs(logs), { total: 3, correct: 2, wrong: 1, accuracy: 66.7 });
  assert.deepEqual(summarizeLogs([]), { total: 0, correct: 0, wrong: 0, accuracy: 0 });
});

test("kstDateKey: UTC 자정 직전도 한국 날짜로 센다", () => {
  assert.equal(kstDateKey("2026-11-01T15:30:00.000Z"), "2026-11-02", "KST 00:30 은 다음 날이다");
  assert.equal(kstDateKey("2026-11-02T05:30:00.000Z"), "2026-11-02");
  assert.equal(kstDateKey("잘못된 값"), "");
});

test("kstTime: 한국 시각의 HH:mm", () => {
  assert.equal(kstTime("2026-11-02T05:30:00.000Z"), "14:30");
  assert.equal(kstTime("nope"), "");
});

test("groupByKstDate: 최신순 입력을 한국 날짜별로 묶고 순서를 유지한다", () => {
  const logs = [
    { term: "a", created_at: "2026-11-01T15:45:00.000Z" }, // KST 11-02 00:45
    { term: "b", created_at: "2026-11-02T01:00:00.000Z" }, // KST 11-02 10:00
    { term: "c", created_at: "2026-11-01T01:00:00.000Z" }, // KST 11-01 10:00
  ];
  const groups = groupByKstDate(logs);
  assert.deepEqual(groups.map((g) => g.date), ["2026-11-02", "2026-11-01"]);
  assert.deepEqual(groups[0].items.map((l) => l.term), ["a", "b"]);
});

test("uniqueWrongWordIds: 틀린 답이 있었던 단어만 고유하게 모은다", () => {
  const logs = [
    { word_id: 1, is_correct: false },
    { word_id: 1, is_correct: false },
    { word_id: 2, is_correct: true },
    { word_id: 3, is_correct: false },
  ];
  assert.deepEqual([...uniqueWrongWordIds(logs)].sort(), [1, 3]);
  assert.equal(uniqueWrongWordIds([]).size, 0);
});
