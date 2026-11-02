/*
 * 2026-11-02 - voda-voca - 학습 통계 계산 단위 테스트: 요약(총 단어, 정답률, 연속 학습일), 최근 7일 활동, 단어장 진행률 엣지 케이스
 * 파일 위치: src/frontend/tests/stats.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { computeSummary, computeStreak, computeWeeklyActivity, computeWordbookProgress, kstDayKeyOf } from "../js/core/stats.js";

// 기준 시각: 한국 2026-11-02 15:00 (UTC 06:00)
const NOW = Date.parse("2026-11-02T06:00:00Z");

const log = (word_id, wordbook_id, is_correct, created_at) => ({ word_id, wordbook_id, is_correct, created_at });

test("한국 날짜 키는 UTC 자정이 아니라 한국 자정으로 나뉜다", () => {
  assert.equal(kstDayKeyOf(Date.parse("2026-11-01T14:59:59Z")), "2026-11-01"); // KST 23:59:59
  assert.equal(kstDayKeyOf(Date.parse("2026-11-01T15:00:00Z")), "2026-11-02"); // KST 00:00:00
});

test("요약: 총 단어 수는 단어장 합계, 정답률은 반올림한 백분율", () => {
  const books = [{ word_count: 200 }, { word_count: 1000 }, { word_count: 0 }];
  const logs = [log(1, 10, true, "2026-11-02T01:00:00Z"), log(2, 10, true, "2026-11-02T01:01:00Z"), log(3, 10, false, "2026-11-02T01:02:00Z")];
  assert.deepEqual(computeSummary(books, logs, NOW), { totalWords: 1200, answered: 3, accuracy: 67, streak: 1 });
});

test("요약: 학습 기록이 없으면 정답률은 null, 연속 학습일은 0", () => {
  assert.deepEqual(computeSummary([], [], NOW), { totalWords: 0, answered: 0, accuracy: null, streak: 0 });
  assert.equal(computeSummary([{ word_count: 5 }], [], NOW).accuracy, null);
});

test("연속 학습일: 오늘부터 끊기지 않은 날 수를 센다", () => {
  const logs = [
    log(1, 10, true, "2026-11-02T01:00:00Z"), // 11-02 KST
    log(2, 10, true, "2026-11-01T03:00:00Z"), // 11-01 KST
    log(3, 10, true, "2026-10-31T03:00:00Z"), // 10-31 KST
    log(4, 10, true, "2026-10-29T03:00:00Z"), // 10-29 KST (10-30 빠짐)
  ];
  assert.equal(computeStreak(logs, NOW), 3);
});

test("연속 학습일: 오늘 아직 학습하지 않았으면 어제부터 센다", () => {
  const logs = [log(1, 10, true, "2026-11-01T03:00:00Z"), log(2, 10, true, "2026-10-31T03:00:00Z")];
  assert.equal(computeStreak(logs, NOW), 2);
  assert.equal(computeStreak([log(1, 10, true, "2026-10-30T03:00:00Z")], NOW), 0);
});

test("연속 학습일: 잘못된 날짜 문자열은 무시한다", () => {
  const logs = [log(1, 10, true, "not-a-date"), log(2, 10, true, "2026-11-02T01:00:00Z")];
  assert.equal(computeStreak(logs, NOW), 1);
});

test("최근 7일 활동: 오래된 날부터 오늘까지 7칸, 요일 라벨과 날짜 키를 준다", () => {
  const days = computeWeeklyActivity([], NOW);
  assert.equal(days.length, 7);
  assert.deepEqual(days[0], { date: "2026-10-27", label: "화", count: 0 });
  assert.deepEqual(days[6], { date: "2026-11-02", label: "월", count: 0 });
});

test("최근 7일 활동: 같은 날 같은 단어를 여러 번 풀어도 한 번으로 센다", () => {
  const logs = [
    log(1, 10, true, "2026-11-02T01:00:00Z"),
    log(1, 10, false, "2026-11-02T01:05:00Z"),
    log(2, 10, true, "2026-11-02T01:06:00Z"),
    log(3, 10, true, "2026-11-01T02:00:00Z"),
  ];
  const days = computeWeeklyActivity(logs, NOW);
  assert.equal(days[6].count, 2);
  assert.equal(days[5].count, 1);
});

test("최근 7일 활동: 7일보다 오래된 기록과 범위 밖 날짜는 집계하지 않는다", () => {
  const logs = [log(1, 10, true, "2026-10-26T12:00:00Z"), log(2, 10, true, "2026-11-03T03:00:00Z")];
  const days = computeWeeklyActivity(logs, NOW);
  assert.equal(days.reduce((sum, day) => sum + day.count, 0), 0);
});

test("최근 7일 활동: 한국 자정 경계에서 날짜가 갈린다", () => {
  const logs = [log(1, 10, true, "2026-10-31T14:59:00Z"), log(2, 10, true, "2026-10-31T15:01:00Z")]; // KST 10-31 23:59, 11-01 00:01
  const days = computeWeeklyActivity(logs, NOW);
  assert.equal(days.find((d) => d.date === "2026-10-31").count, 1);
  assert.equal(days.find((d) => d.date === "2026-11-01").count, 1);
});

test("단어장 진행률: 정답 이력이 있는 고유 단어의 비율", () => {
  const logs = [log(1, 10, true, "x"), log(1, 10, true, "x"), log(2, 10, false, "x"), log(3, 10, true, "x"), log(9, 20, true, "x")];
  assert.equal(computeWordbookProgress(10, logs, 4), 50); // 정답 단어 1, 3 → 2/4
});

test("단어장 진행률 엣지: 학습 기록이 없으면 0", () => {
  assert.equal(computeWordbookProgress(10, [], 200), 0);
  assert.equal(computeWordbookProgress(10, [log(1, 20, true, "x")], 200), 0); // 다른 단어장의 기록
});

test("단어장 진행률 엣지: 단어가 0개이면 0 (0으로 나누지 않는다)", () => {
  assert.equal(computeWordbookProgress(10, [log(1, 10, true, "x")], 0), 0);
  assert.equal(computeWordbookProgress(10, [log(1, 10, true, "x")], Number.NaN), 0);
});

test("단어장 진행률: 100%를 넘지 않는다", () => {
  const logs = [log(1, 10, true, "x"), log(2, 10, true, "x"), log(3, 10, true, "x")];
  assert.equal(computeWordbookProgress(10, logs, 2), 100);
});
