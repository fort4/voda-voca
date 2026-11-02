/*
 * 2026-11-02 - voda-voca - 학습 통계 계산: 요약(총 단어, 정답률, 연속 학습일), 최근 7일 활동, 단어장 진행률 (순수 함수, DOM 없음)
 * 파일 위치: src/frontend/js/core/stats.js
 */

const DAY_MS = 24 * 60 * 60 * 1000;
const KST_OFFSET_MS = 9 * 60 * 60 * 1000; // 학습일 경계는 한국 시각 자정으로 본다
const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

/**
 * 시각(ms)을 한국 날짜 키 YYYY-MM-DD 로 바꾼다.
 * @param {number} ms
 * @returns {string}
 */
export function kstDayKeyOf(ms) {
  return new Date(ms + KST_OFFSET_MS).toISOString().slice(0, 10);
}

/**
 * ISO 시각 문자열을 한국 날짜 키로 바꾼다. 잘못된 값이면 빈 문자열.
 * @param {string} iso
 * @returns {string}
 */
function dayKeyOfIso(iso) {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? "" : kstDayKeyOf(ms);
}

/** @param {string} key YYYY-MM-DD @param {number} delta 일 수 @returns {string} */
function shiftDayKey(key, delta) {
  return new Date(Date.parse(`${key}T00:00:00Z`) + delta * DAY_MS).toISOString().slice(0, 10);
}

/**
 * 연속 학습일: 오늘(한국 날짜)부터 거꾸로 학습 기록이 끊기지 않은 날 수.
 * 오늘 아직 학습하지 않았다면 어제부터 센다 (하루가 끝나기 전에 연속이 깨지지 않도록).
 * @param {Array<{created_at: string}>} studyLogs
 * @param {number} now 기준 시각 (ms)
 * @returns {number}
 */
export function computeStreak(studyLogs, now) {
  const days = new Set(studyLogs.map((log) => dayKeyOfIso(log.created_at)).filter(Boolean));
  let day = kstDayKeyOf(now);
  if (!days.has(day)) day = shiftDayKey(day, -1);
  let streak = 0;
  while (days.has(day)) {
    streak += 1;
    day = shiftDayKey(day, -1);
  }
  return streak;
}

/**
 * 대시보드 요약.
 * - totalWords: 모든 단어장의 단어 수 합계
 * - accuracy: 정답률 (%, 반올림). 학습 기록이 없으면 null
 * - answered: 집계한 문항 수
 * - streak: 연속 학습일
 * @param {Array<{word_count: number}>} wordbooks
 * @param {Array<{is_correct: boolean, created_at: string}>} studyLogs
 * @param {number} [now=Date.now()]
 */
export function computeSummary(wordbooks, studyLogs, now = Date.now()) {
  const totalWords = wordbooks.reduce((sum, book) => sum + (Number.isInteger(book.word_count) ? book.word_count : 0), 0);
  const answered = studyLogs.length;
  const correct = studyLogs.filter((log) => log.is_correct === true).length;
  return {
    totalWords,
    answered,
    accuracy: answered === 0 ? null : Math.round((correct / answered) * 100),
    streak: computeStreak(studyLogs, now),
  };
}

/**
 * 최근 7일(오늘 포함) 일자별 학습한 단어 수. 같은 단어를 같은 날 여러 번 풀어도 한 번으로 센다.
 * @param {Array<{word_id: number, created_at: string}>} studyLogs
 * @param {number} [now=Date.now()]
 * @returns {Array<{date: string, label: string, count: number}>} 오래된 날부터 오늘 순서
 */
export function computeWeeklyActivity(studyLogs, now = Date.now()) {
  const today = kstDayKeyOf(now);
  const keys = Array.from({ length: 7 }, (_, i) => shiftDayKey(today, i - 6));
  const wordsByDay = new Map(keys.map((key) => [key, new Set()]));
  for (const log of studyLogs) {
    const bucket = wordsByDay.get(dayKeyOfIso(log.created_at));
    if (bucket) bucket.add(log.word_id);
  }
  return keys.map((key) => ({
    date: key,
    label: WEEK_LABELS[new Date(`${key}T00:00:00Z`).getUTCDay()],
    count: wordsByDay.get(key).size,
  }));
}

/**
 * 단어장 진행률 (%): 그 단어장 단어 중 정답 이력이 있는 단어의 비율.
 * 학습 기록에 없는 단어장이거나 단어가 없으면 0. 100을 넘지 않는다.
 * @param {number} wordbookId
 * @param {Array<{word_id: number, wordbook_id: number, is_correct: boolean}>} studyLogs
 * @param {number} wordCount 단어장의 단어 수
 * @returns {number}
 */
export function computeWordbookProgress(wordbookId, studyLogs, wordCount) {
  if (!Number.isInteger(wordCount) || wordCount <= 0) return 0;
  const correctWords = new Set(
    studyLogs.filter((log) => log.wordbook_id === wordbookId && log.is_correct === true).map((log) => log.word_id),
  );
  return Math.min(100, Math.round((correctWords.size / wordCount) * 100));
}
