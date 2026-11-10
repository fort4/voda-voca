/*
 * 2026-11-05 - voda-voca - 홈 화면 뷰모델 테스트: 활성 단어장, 오늘 목표·남은 문항, 학습 CTA, 모드 기억
 * 파일 위치: src/frontend/tests/home-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import * as homeModule from "../js/core/home-model.js";
import { homeModel, loadMode, saveMode, startPath } from "../js/core/home-model.js";
import { FALLBACK_SETTINGS } from "../js/core/settings-model.js";

const active = { id: 2, title: "중고등 기본 1,000제", total_words: 1000, user_progress: { studied_words: 520, memorized_words: 140, progress_rate: 52, is_active: true } };
const stats = (todayCount, streak = 3) => ({
  streak_days: streak,
  weekly: [
    { date: "2026-11-04", label: "수", count: 9, is_today: false },
    { date: "2026-11-05", label: "목", count: todayCount, is_today: true },
  ],
});

const settings = (daily_goal) => ({ ...FALLBACK_SETTINGS, daily_goal });

test("하루 목표·세션 크기 상수는 없다 (사용자 설정으로 대체, REQ-147)", () => {
  assert.equal("DAILY_GOAL" in homeModule, false);
  assert.equal("SESSION_SIZE" in homeModule, false);
});

test("목표는 설정의 daily_goal 을 따르고, 설정이 없으면 10", () => {
  assert.equal(homeModel({ active, stats: stats(6), settings: settings(30) }).remaining, 24);
  assert.equal(homeModel({ active, stats: stats(6), settings: settings(20) }).goalPercent, 30);
  assert.equal(homeModel({ active, stats: stats(6) }).remaining, 4);
  assert.equal(homeModel({ active, stats: stats(10), settings: settings(10) }).goalReached, true);
  assert.equal(homeModel({ active, stats: stats(10), settings: settings(20) }).goalReached, false);
  assert.equal(homeModel({ active, stats: stats(6), settings: settings(20) }).dailyGoal, 20);
});

test("오늘 푼 수가 목표보다 적으면 남은 수를 센다", () => {
  const m = homeModel({ active, stats: stats(6), settings: settings(15 + 5) });
  assert.equal(m.todayCount, 6);
  assert.equal(m.remaining, 14);
  assert.equal(m.goalReached, false);
  assert.equal(m.goalPercent, 30);
});

test("목표를 넘기면 남은 수는 0 이고 진행률은 100 으로 멈춘다", () => {
  const m = homeModel({ active, stats: stats(22), settings: settings(20) });
  assert.equal(m.remaining, 0);
  assert.equal(m.goalPercent, 100);
  assert.equal(m.goalReached, true);
});

test("오늘 항목이 weekly 에 없으면 0 으로 본다", () => {
  const m = homeModel({ active, stats: { streak_days: 0, weekly: [] } });
  assert.equal(m.todayCount, 0);
  assert.equal(m.remaining, 10);
});

test("연속 학습일이 0 이면 숨기고, 있으면 문구를 준다", () => {
  assert.equal(homeModel({ active, stats: stats(0, 0) }).streakText, null);
  assert.equal(homeModel({ active, stats: stats(0, 5) }).streakText, "5일 연속");
});

test("활성 단어장 요약: 제목과 진행 문구", () => {
  const m = homeModel({ active, stats: stats(0) });
  assert.equal(m.hasActive, true);
  assert.equal(m.vocabularyTitle, "중고등 기본 1,000제");
  assert.equal(m.progressPercent, 52);
  assert.equal(m.progressText, "520 / 1,000 학습");
});

test("활성 단어장이 없으면 CTA 를 막고 탐색으로 안내한다", () => {
  const m = homeModel({ active: null, stats: stats(0) });
  assert.equal(m.hasActive, false);
  assert.equal(m.canStart, false);
  assert.equal(m.emptyHint, "학습할 단어장을 먼저 골라 주세요.");
});

test("활성 단어장이 있으면 시작할 수 있다", () => {
  assert.equal(homeModel({ active, stats: stats(0) }).canStart, true);
});

test("통계를 아직 못 받았으면(null) 목표 영역은 값 없음으로 둔다", () => {
  const m = homeModel({ active, stats: null });
  assert.equal(m.todayCount, null);
  assert.equal(m.remaining, null);
  assert.equal(m.streakText, null);
  assert.equal(m.canStart, true);
});

test("시작 경로: 모드를 쿼리로 넘긴다", () => {
  assert.equal(startPath("quiz"), "/study/session?mode=quiz");
  assert.equal(startPath("flashcard"), "/study/session?mode=flashcard");
  assert.equal(startPath("이상한값"), "/study/session?mode=quiz");
});

test("모드 기억: 저장한 값을 읽고, 없거나 깨졌으면 quiz", () => {
  const store = new Map();
  const storage = { getItem: (k) => store.get(k) ?? null, setItem: (k, v) => store.set(k, v) };
  assert.equal(loadMode(storage), "quiz");
  saveMode(storage, "flashcard");
  assert.equal(loadMode(storage), "flashcard");
  store.set("voda.study.mode", "garbage");
  assert.equal(loadMode(storage), "quiz");
});

test("모드 기억: 저장소가 없거나 예외를 던져도 화면이 죽지 않는다", () => {
  const broken = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.equal(loadMode(broken), "quiz");
  assert.equal(loadMode(undefined), "quiz");
  assert.doesNotThrow(() => saveMode(broken, "flashcard"));
  assert.doesNotThrow(() => saveMode(undefined, "flashcard"));
});
