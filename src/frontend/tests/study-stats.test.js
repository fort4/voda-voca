/*
 * 2026-11-03 - voda-voca - 한국 날짜 묶음 단위 테스트, 시각 표시 (REQ-016)
 * 파일 위치: src/frontend/tests/study-stats.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { kstDateKey, kstTime } from "../js/core/format.js";
import { groupByKstDate } from "../js/lib/study-stats.js";

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
