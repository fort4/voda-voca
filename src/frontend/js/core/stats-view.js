/*
 * 2026-11-03 - voda-voca - 학습 통계 화면 값: 서버 통계(/study/stats)를 대시보드 카드, 이력 요약, 오답 복습 안내 문구로 바꾼다 (이슈 #3)
 * 파일 위치: src/frontend/js/core/stats-view.js
 */

import { QUIZ_MIN_WORDS } from "../lib/study-source.js";

export const HISTORY_TIMELINE_LIMIT = 100; // 이력 화면의 타임라인에 보이는 최근 기록 수 (/study/logs 의 최대치)

const KO = "ko-KR";
const NO_DATA = "—";

/** @param {number} n */
const formatCount = (n) => n.toLocaleString(KO);

/**
 * 서버 통계 응답을 대시보드가 그릴 값으로 바꾼다. 계산은 서버가 했고, 여기서는 표시 문구만 만든다.
 * @param {{answered: number, accuracy: number|null, streak_days: number, total_words: number,
 *          weekly: Array<{date: string, label: string, count: number, is_today: boolean}>,
 *          wordbook_progress: Array<{wordbook_id: number, percent: number}>}} stats
 */
export function dashboardModel(stats) {
  const weekly = stats.weekly.map((day) => ({ date: day.date, label: day.label, count: day.count, isToday: day.is_today }));
  const progress = new Map(stats.wordbook_progress.map((p) => [p.wordbook_id, p.percent]));
  return {
    totalWords: formatCount(stats.total_words),
    accuracy:
      stats.accuracy === null
        ? { value: NO_DATA, hint: "기록 없음" }
        : { value: `${Math.round(stats.accuracy)}%`, hint: `누적 ${formatCount(stats.answered)}문항` },
    streak: { value: `${stats.streak_days}일`, hint: "오늘 기준" },
    weekly,
    weekTotal: weekly.reduce((sum, day) => sum + day.count, 0),
    /** @param {number} wordbookId @returns {number} 진행률(0~100). 모르는 단어장은 0 */
    progressOf: (wordbookId) => progress.get(wordbookId) ?? 0,
  };
}

/**
 * 이력 화면 상단 요약. 정답률은 누적 기준이고, 아래 타임라인은 최근 기록만 보인다는 점을 밝힌다.
 * @param {{answered: number, correct: number, accuracy: number|null}} stats
 */
export function historySummary(stats) {
  return {
    headline: stats.accuracy === null ? NO_DATA : `${stats.accuracy}%`,
    detail: `누적 ${formatCount(stats.answered)}문항 중 정답 ${formatCount(stats.correct)}개, 오답 ${formatCount(stats.answered - stats.correct)}개`,
    footnote: `아래 기록은 최근 ${HISTORY_TIMELINE_LIMIT}건까지 보여 줍니다.`,
  };
}

/**
 * 오답 복습 퀴즈를 시작할 수 있는지와 안내 문구. 퀴즈 출제의 최소 단어 수(4개)와 같은 기준이다.
 * @param {number} wrongWordCount 단어별 마지막 결과가 오답인 단어 수
 * @returns {{ready: boolean, message: string}}
 */
export function wrongReviewState(wrongWordCount) {
  const ready = wrongWordCount >= QUIZ_MIN_WORDS;
  return {
    ready,
    message: ready
      ? `틀린 단어 ${wrongWordCount}개로 복습합니다.`
      : `복습 가능한 오답 단어가 ${QUIZ_MIN_WORDS}개 이상이어야 합니다 (현재 ${wrongWordCount}개).`,
  };
}
