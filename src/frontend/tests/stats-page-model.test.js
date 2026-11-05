/*
 * 2026-11-05 - voda-voca - 통계 화면 뷰모델 테스트: 표준 단어장 체계의 누적 지표, 연속 학습일, 주간 활동, 단어장별 진행률
 * 파일 위치: src/frontend/tests/stats-page-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { statsPageModel } from "../js/core/stats-page-model.js";

const stats = (over = {}) => ({
  answered: 1234,
  correct: 987,
  accuracy: 80.0,
  streak_days: 4,
  weekly: [
    { date: "2026-11-04", label: "수", count: 9, is_today: false },
    { date: "2026-11-05", label: "목", count: 6, is_today: true },
  ],
  total_words: 3000,
  vocabulary_progress: [
    { vocabulary_id: 1, word_count: 500, learned_words: 120, percent: 24 },
    { vocabulary_id: 2, word_count: 1000, learned_words: 0, percent: 0 },
  ],
  wrong_word_count: 7,
  ...over,
});
const catalog = [
  { id: 1, title: "초등 필수", user_progress: { is_active: false, memorized_words: 30 } },
  { id: 2, title: "중고등 기본", user_progress: { is_active: true, memorized_words: 0 } },
];

test("요약 카드: 정답률·누적 문항·연속 학습일 문구", () => {
  const m = statsPageModel(stats(), catalog);
  assert.deepEqual(m.accuracy, { value: "80%", hint: "누적 1,234문항" });
  assert.deepEqual(m.streak, { value: "4일", hint: "오늘 기준" });
  assert.equal(m.totalWords, "3,000");
  assert.equal(m.wrongWordCount, 7);
});

test("푼 문항이 없으면 정답률은 '—' 와 '기록 없음'", () => {
  const m = statsPageModel(stats({ answered: 0, correct: 0, accuracy: null }), catalog);
  assert.deepEqual(m.accuracy, { value: "—", hint: "기록 없음" });
});

test("연속 학습일이 0 이면 숨길 수 있게 null", () => {
  assert.equal(statsPageModel(stats({ streak_days: 0 }), catalog).streak, null);
});

test("주간 활동: 합계와 오늘 표시, 막대 높이 비율(최대값 기준)", () => {
  const m = statsPageModel(stats(), catalog);
  assert.equal(m.weekTotal, 15);
  assert.deepEqual(m.weekly.map((d) => d.isToday), [false, true]);
  assert.deepEqual(m.weekly.map((d) => d.ratio), [1, 6 / 9]);
});

test("주간 활동이 전부 0 이면 비율도 0 (0 으로 나누지 않는다)", () => {
  const m = statsPageModel(stats({ weekly: [{ date: "d", label: "목", count: 0, is_today: true }] }), catalog);
  assert.deepEqual(m.weekly.map((d) => d.ratio), [0]);
});

test("단어장별 진행률: 카탈로그의 제목·활성 여부를 붙이고 진행 문구를 만든다", () => {
  const m = statsPageModel(stats(), catalog);
  assert.equal(m.vocabularies.length, 2);
  assert.deepEqual(m.vocabularies[0], { id: 1, title: "초등 필수", percent: 24, isActive: false, text: "120 / 500 학습" });
  assert.equal(m.vocabularies[1].isActive, true);
});

test("활성 단어장을 맨 앞에 두고 나머지는 원래 순서를 지킨다", () => {
  const m = statsPageModel(stats(), catalog);
  assert.deepEqual(m.vocabulariesActiveFirst.map((v) => v.id), [2, 1]);
});

test("카탈로그에 없는 단어장 ID 는 제목 대신 대체 문구를 쓴다 (화면이 죽지 않는다)", () => {
  const m = statsPageModel(stats({ vocabulary_progress: [{ vocabulary_id: 99, word_count: 10, learned_words: 1, percent: 10 }] }), catalog);
  assert.equal(m.vocabularies[0].title, "단어장 99");
});

test("카탈로그를 못 받았어도(null) 통계 자체는 계산된다", () => {
  const m = statsPageModel(stats(), null);
  assert.equal(m.accuracy.value, "80%");
  assert.equal(m.vocabularies[0].title, "단어장 1");
});

test("전체 학습 이력이 비었는지(빈 상태) 판정한다", () => {
  assert.equal(statsPageModel(stats({ answered: 0, accuracy: null }), catalog).isEmpty, true);
  assert.equal(statsPageModel(stats(), catalog).isEmpty, false);
});
