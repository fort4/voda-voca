/*
 * 2026-11-03 - voda-voca - 학습 이력 한국 날짜별 묶음 (순수 함수, REQ-016). 정답률·오답 단어 집계는 서버 통계로 옮겼다 (이슈 #3)
 * 파일 위치: src/frontend/js/lib/study-stats.js
 */

import { kstDateKey } from "../core/format.js";

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
