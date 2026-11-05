/*
 * 2026-11-03 - voda-voca - 한국 날짜 키·시각 표시 단위 테스트 (REQ-016)
 * 파일 위치: src/frontend/tests/format-kst.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { kstDateKey, kstTime } from "../js/core/format.js";

test("kstDateKey: UTC 자정 직전도 한국 날짜로 센다", () => {
  assert.equal(kstDateKey("2026-11-01T15:30:00.000Z"), "2026-11-02", "KST 00:30 은 다음 날이다");
  assert.equal(kstDateKey("2026-11-02T05:30:00.000Z"), "2026-11-02");
  assert.equal(kstDateKey("잘못된 값"), "");
});

test("kstTime: 한국 시각의 HH:mm", () => {
  assert.equal(kstTime("2026-11-02T05:30:00.000Z"), "14:30");
  assert.equal(kstTime("nope"), "");
});
