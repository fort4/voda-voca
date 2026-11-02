/*
 * 2026-11-02 - voda-voca - 제스처 판정 단위 테스트: 탭, 좌우 스와이프 임계값, 세로 스크롤 무시 (UI 설계서 §7)
 * 파일 위치: src/frontend/tests/gesture.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { classifyGesture, SWIPE_MIN_PX, TAP_MAX_MOVE_PX } from "../js/core/gesture.js";

test("8px 미만 이동은 탭이다", () => {
  assert.equal(classifyGesture(0, 0), "tap");
  assert.equal(classifyGesture(TAP_MAX_MOVE_PX - 1, 3), "tap");
});

test("48px 이상 가로로 밀면 왼쪽은 다음, 오른쪽은 이전이다", () => {
  assert.equal(classifyGesture(-SWIPE_MIN_PX, 2), "next");
  assert.equal(classifyGesture(SWIPE_MIN_PX + 10, -4), "prev");
});

test("임계값 미만의 가로 이동은 아무것도 아니다 (null)", () => {
  assert.equal(classifyGesture(-30, 5), null);
});

test("세로 이동이 더 크면 스크롤로 보고 무시한다", () => {
  assert.equal(classifyGesture(60, 120), null);
  assert.equal(classifyGesture(-50, 50), null, "가로와 세로가 같으면 스와이프로 보지 않는다");
});
