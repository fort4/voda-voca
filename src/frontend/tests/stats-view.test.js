/*
 * 2026-11-03 - voda-voca - 학습 통계 화면 값 단위 테스트: 대시보드 카드, 이력 요약, 오답 복습 가능 여부 (이슈 #3)
 * 파일 위치: src/frontend/tests/stats-view.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { dashboardModel, historySummary, wrongReviewState } from "../js/core/stats-view.js";

const STATS = {
  answered: 1234,
  correct: 987,
  accuracy: 80,
  streak_days: 5,
  total_words: 1600,
  wrong_word_count: 7,
  weekly: [
    { date: "2026-10-29", label: "목", count: 3, is_today: false },
    { date: "2026-10-30", label: "금", count: 0, is_today: false },
    { date: "2026-10-31", label: "토", count: 12, is_today: false },
    { date: "2026-11-01", label: "일", count: 0, is_today: false },
    { date: "2026-11-02", label: "월", count: 5, is_today: false },
    { date: "2026-11-03", label: "화", count: 8, is_today: false },
    { date: "2026-11-04", label: "수", count: 2, is_today: true },
  ],
  wordbook_progress: [
    { wordbook_id: 11, word_count: 200, learned_words: 100, percent: 50 },
    { wordbook_id: 12, word_count: 1000, learned_words: 10, percent: 1 },
  ],
};

test("dashboardModel: 카드 값은 누적 기준이고 천 단위 구분을 쓴다", () => {
  const m = dashboardModel(STATS);
  assert.equal(m.totalWords, "1,600");
  assert.equal(m.accuracy.value, "80%");
  assert.equal(m.accuracy.hint, "누적 1,234문항");
  assert.equal(m.streak.value, "5일");
});

test("dashboardModel: 정답률은 반올림해서 보여 준다", () => {
  assert.equal(dashboardModel({ ...STATS, accuracy: 66.7 }).accuracy.value, "67%");
  assert.equal(dashboardModel({ ...STATS, accuracy: 66.4 }).accuracy.value, "66%");
});

test("dashboardModel: 푼 문항이 없으면 정답률은 대시와 '기록 없음'이다 (0% 가 아니다)", () => {
  const m = dashboardModel({ ...STATS, answered: 0, correct: 0, accuracy: null, streak_days: 0 });
  assert.equal(m.accuracy.value, "—");
  assert.equal(m.accuracy.hint, "기록 없음");
  assert.equal(m.streak.value, "0일");
});

test("dashboardModel: 주간 데이터는 차트 입력 형태(isToday)로 바꾸고 합계를 구한다", () => {
  const m = dashboardModel(STATS);
  assert.equal(m.weekly.length, 7);
  assert.deepEqual(m.weekly[6], { date: "2026-11-04", label: "수", count: 2, isToday: true });
  assert.equal(m.weekly[0].isToday, false);
  assert.equal(m.weekTotal, 30);
});

test("dashboardModel: 단어장 진행률은 단어장 ID 로 찾고, 없으면 0 이다", () => {
  const m = dashboardModel(STATS);
  assert.equal(m.progressOf(11), 50);
  assert.equal(m.progressOf(12), 1);
  assert.equal(m.progressOf(999), 0);
});

test("historySummary: 누적 기준 정답률과 문항 수를 보여 주고 타임라인은 최근 100건임을 밝힌다", () => {
  const s = historySummary(STATS);
  assert.equal(s.headline, "80%");
  assert.equal(s.detail, "누적 1,234문항 중 정답 987개, 오답 247개");
  assert.match(s.footnote, /최근 100건/);
});

test("historySummary: 기록이 없으면 대시", () => {
  const s = historySummary({ ...STATS, answered: 0, correct: 0, accuracy: null });
  assert.equal(s.headline, "—");
});

test("wrongReviewState: 오답 단어가 4개 이상이어야 복습을 시작할 수 있다", () => {
  assert.deepEqual(wrongReviewState(7), { ready: true, message: "틀린 단어 7개로 복습합니다." });
  assert.equal(wrongReviewState(4).ready, true);
  const blocked = wrongReviewState(3);
  assert.equal(blocked.ready, false);
  assert.equal(blocked.message, "복습 가능한 오답 단어가 4개 이상이어야 합니다 (현재 3개).");
  assert.equal(wrongReviewState(0).ready, false);
});
