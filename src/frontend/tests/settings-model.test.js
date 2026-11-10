/*
 * 2026-11-10 - voda-voca - 학습 개수 설정 모델 테스트: 서버 응답 정규화, 폴백, 변경 적용, 모드별 문항 수, 시작 버튼 문구 (REQ-147)
 * 파일 위치: src/frontend/tests/settings-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { FALLBACK_SETTINGS, SETTING_ROWS, applySetting, normalizeSettings, sessionSizeFor, startLabel } from "../js/core/settings-model.js";

const server = { quiz_count: 20, flashcard_count: 30, daily_goal: 10, options: [10, 20, 30] };

test("폴백: 서버를 못 받았을 때의 값은 모두 10 이고 옵션은 10/20/30", () => {
  assert.deepEqual(FALLBACK_SETTINGS, { quiz_count: 10, flashcard_count: 10, daily_goal: 10, options: [10, 20, 30] });
  assert.equal(Object.isFrozen(FALLBACK_SETTINGS), true);
});

test("행 정의: 퀴즈 · 플래시카드 · 오늘의 목표 순서", () => {
  assert.deepEqual(SETTING_ROWS.map((r) => [r.key, r.label]), [["quiz_count", "퀴즈"], ["flashcard_count", "플래시카드"], ["daily_goal", "오늘의 목표"]]);
});

test("normalizeSettings: 정상 응답은 그대로 쓴다", () => {
  assert.deepEqual(normalizeSettings(server), server);
});

test("normalizeSettings: 깨진 응답은 폴백, 옵션에 없는 값은 필드별로 10 으로 되돌린다", () => {
  for (const raw of [null, undefined, "x", 3, []]) assert.deepEqual(normalizeSettings(raw), FALLBACK_SETTINGS, String(raw));
  assert.deepEqual(normalizeSettings({ ...server, quiz_count: 15, daily_goal: "20" }), { ...server, quiz_count: 10, daily_goal: 10 });
  assert.deepEqual(normalizeSettings({ ...server, options: [] }).options, [10, 20, 30]);
  assert.deepEqual(normalizeSettings({ ...server, options: [10, "x", -5, 20] }).options, [10, 20]);
});

test("normalizeSettings: 서버가 옵션을 늘리면 그 값을 받아들인다", () => {
  const next = normalizeSettings({ quiz_count: 50, flashcard_count: 10, daily_goal: 10, options: [10, 20, 30, 50] });
  assert.equal(next.quiz_count, 50);
  assert.deepEqual(next.options, [10, 20, 30, 50]);
});

test("applySetting: 값을 바꾼 새 객체를 돌려주고 원본은 건드리지 않는다", () => {
  const next = applySetting(server, "daily_goal", 30);
  assert.equal(next.daily_goal, 30);
  assert.equal(server.daily_goal, 10);
  assert.notEqual(next, server);
});

test("applySetting: 옵션에 없는 값·모르는 키·같은 값은 같은 객체를 돌려준다 (변경 없음)", () => {
  assert.equal(applySetting(server, "daily_goal", 15), server);
  assert.equal(applySetting(server, "nickname", 10), server);
  assert.equal(applySetting(server, "quiz_count", 20), server);
});

test("sessionSizeFor: 모드에 맞는 설정을 고르고, 모르는 모드는 퀴즈", () => {
  assert.equal(sessionSizeFor(server, "quiz"), 20);
  assert.equal(sessionSizeFor(server, "flashcard"), 30);
  assert.equal(sessionSizeFor(server, "이상한값"), 20);
});

test("startLabel: 현재 모드의 문항 수로 시작 버튼 문구를 만든다", () => {
  assert.equal(startLabel(server, "quiz"), "20문항 학습 시작");
  assert.equal(startLabel(server, "flashcard"), "30문항 학습 시작");
});
