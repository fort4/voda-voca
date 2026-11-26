/*
 * 2026-11-26 - voda-voca - 홈의 일차 진도 표시 검사: 현재 일차, 그 일차의 학습 단어, 암기한 단어 수 / 전체 (REQ-165)
 * 파일 위치: src/frontend/tests/study-day.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { homeModel } from "../js/core/home-model.js";
import { FALLBACK_SETTINGS } from "../js/core/settings-model.js";

const active = { id: 2, title: "초급", total_words: 1200, user_progress: { studied_words: 40, memorized_words: 12, progress_rate: 3, is_active: true } };
const stats = (day_progress) => ({ streak_days: 1, weekly: [], day_progress });
const day = (n, words, vocabulary_id = 2) => stats({ vocabulary_id, day: n, words });
const settings = (daily_goal) => ({ ...FALLBACK_SETTINGS, daily_goal });

test("현재 일차와 그 일차에 학습한 단어 / 학습량을 보인다", () => {
  const m = homeModel({ active, stats: day(2, 3), settings: settings(10) });

  assert.deepEqual(m.studyDay, { label: "2일차", detail: "이번 일차 3 / 10단어" });
});

test("학습량은 지금 설정을 따른다", () => {
  assert.equal(homeModel({ active, stats: day(1, 6), settings: settings(20) }).studyDay.detail, "이번 일차 6 / 20단어");
});

test("학습량을 채우면 다음 일차가 언제 시작되는지 알린다", () => {
  const m = homeModel({ active, stats: day(3, 12), settings: settings(10) });

  assert.deepEqual(m.studyDay, { label: "3일차", detail: "학습량을 채웠어요 (12 / 10단어). 다음 학습일에 4일차" });
});

test("암기한 단어 수 / 전체를 보인다", () => {
  assert.equal(homeModel({ active, stats: day(1, 0) }).memorizedText, "암기 12 / 1,200단어");
});

test("일차 정보가 없거나 다른 단어장의 것이면 일차를 숨기고, 암기 수는 그대로 보인다", () => {
  for (const value of [null, stats(null), stats(undefined), day(5, 1, 99)]) {
    const m = homeModel({ active, stats: value });
    assert.equal(m.studyDay, null);
    assert.equal(m.memorizedText, "암기 12 / 1,200단어");
  }
});

test("학습 중인 단어장이 없으면 둘 다 없다", () => {
  const m = homeModel({ active: null, stats: day(1, 0) });

  assert.equal(m.studyDay, null);
  assert.equal(m.memorizedText, null);
});

test("홈 화면은 일차와 암기 수를 그린다", () => {
  const view = readFileSync(new URL("../js/views/home-view.js", import.meta.url), "utf8");

  for (const name of ["m.studyDay.label", "m.studyDay.detail", "m.memorizedText"]) assert.ok(view.includes(name), name);
});
