/*
 * 2026-11-02 - voda-voca - 학습 이력 집계: 정답률 요약, 한국 날짜별 묶음 (순수 함수, REQ-016)
 * 파일 위치: src/frontend/js/lib/study-stats.js
 */

import { kstDateKey } from "../core/format.js";

/**
 * @param {Array<{is_correct: boolean}>} logs
 * @returns {{total: number, correct: number, wrong: number, accuracy: number}}
 */
export function summarizeLogs(logs) {
  const total = logs.length;
  const correct = logs.filter((log) => log.is_correct).length;
  return {
    total,
    correct,
    wrong: total - correct,
    accuracy: total ? Math.round((correct / total) * 1000) / 10 : 0,
  };
}

/**
 * 이력을 한국 날짜(YYYY-MM-DD)별로 묶는다. 입력이 최신순이면 결과도 최신순이다.
 * @param {Array<{created_at: string}>} logs
 * @returns {Array<{date: string, items: any[]}>}
 */
export function groupByKstDate(logs) {
  const groups = [];
  const index = new Map();
  for (const log of logs) {
    const date = kstDateKey(log.created_at);
    if (!index.has(date)) {
      const group = { date, items: [] };
      index.set(date, group);
      groups.push(group);
    }
    index.get(date).items.push(log);
  }
  return groups;
}

/**
 * 학습 기록에서 틀린 답이 있었던 단어 ID 의 집합 (고유). 오답 복습 퀴즈의 출제 원천 개수와 같은 기준이다.
 * @param {Array<{word_id: number, is_correct: boolean}>} logs
 * @returns {Set<number>}
 */
export function uniqueWrongWordIds(logs) {
  return new Set(logs.filter((log) => !log.is_correct).map((log) => log.word_id));
}
