/*
 * 2026-11-02 - voda-voca - 세션 타이머 계산 단위 테스트: 서버 Date 보정, 잔여 시간 하한, mm:ss 올림, 5분 경고 (API 규격 §6)
 * 파일 위치: src/frontend/tests/timer.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { computeClockOffset, formatClock, isWarning, remainingMs, WARNING_MS } from "../js/core/timer.js";

test("computeClockOffset: 서버 Date 헤더와 기기 시각의 차이(서버 - 기기)", () => {
  const client = Date.parse("2026-11-02T05:00:00Z");
  assert.equal(computeClockOffset("Mon, 02 Nov 2026 05:00:30 GMT", client), 30_000);
  assert.equal(computeClockOffset("Mon, 02 Nov 2026 04:59:00 GMT", client), -60_000);
});

test("computeClockOffset: 헤더가 없거나 잘못되면 0", () => {
  assert.equal(computeClockOffset(null, 123), 0);
  assert.equal(computeClockOffset("not a date", 123), 0);
});

test("remainingMs: 만료까지 남은 시간, 보정값을 반영한다", () => {
  const expires = "2026-11-02T05:30:00.000Z";
  const now = Date.parse("2026-11-02T05:00:00.000Z");
  assert.equal(remainingMs(expires, now, 0), 30 * 60_000);
  assert.equal(remainingMs(expires, now, 60_000), 29 * 60_000, "서버가 1분 앞서 있으면 1분 적게 남는다");
});

test("remainingMs: 만료 후에는 0 이고 음수가 되지 않는다", () => {
  const expires = "2026-11-02T05:30:00.000Z";
  assert.equal(remainingMs(expires, Date.parse("2026-11-02T06:00:00Z"), 0), 0);
  assert.equal(remainingMs("잘못된 값", 0, 0), 0);
});

test("formatClock: mm:ss 이고 초는 올림한다", () => {
  assert.equal(formatClock(30 * 60_000), "30:00");
  assert.equal(formatClock(65_000), "01:05");
  assert.equal(formatClock(200), "00:01", "0.2초 남아도 00:01");
  assert.equal(formatClock(0), "00:00");
  assert.equal(formatClock(-5), "00:00");
});

test("isWarning: 5분 이하에서만 경고이고 0 은 경고가 아니다", () => {
  assert.equal(WARNING_MS, 300_000);
  assert.equal(isWarning(WARNING_MS), true);
  assert.equal(isWarning(WARNING_MS + 1), false);
  assert.equal(isWarning(0), false);
});
