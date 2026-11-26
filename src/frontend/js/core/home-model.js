/*
 * 2026-11-05 - voda-voca - 홈 화면 뷰모델: 활성 단어장 요약, 오늘 목표·남은 문항(사용자 설정), 일차 진도와 암기 단어 수(REQ-165), 학습 시작 경로, 마지막 모드 기억 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/home-model.js
 */

import { FALLBACK_SETTINGS } from "./settings-model.js";

const MODE_KEY = "voda.study.mode";
const QUIZ_OPTIONS_KEY = "voda.study.quiz-options";
const DEFAULT_QUIZ_OPTIONS = Object.freeze({ direction: "en_to_ko", format: "choice" });
const DIRECTIONS = ["en_to_ko", "ko_to_en", "mixed"];
const FORMATS = ["choice", "ox"];
const KO = "ko-KR";

/** @param {unknown} mode @returns {"quiz"|"flashcard"} 알 수 없는 값은 quiz */
const normalizeMode = (mode) => (mode === "flashcard" ? "flashcard" : "quiz");

/**
 * 홈이 그릴 값.
 * @param {{active: null|{title: string, total_words: number, user_progress: {studied_words: number, progress_rate: number}},
 *          stats: null|{streak_days: number, weekly: Array<{count: number, is_today: boolean}>,
 *                       day_progress?: null|{vocabulary_id: number, day: number, words: number}}}} input
 *   stats 가 null 이면 아직 못 받은 것이다 (목표 영역은 값 없음으로 둔다).
 */
export function homeModel({ active, stats, settings = FALLBACK_SETTINGS }) {
  const goal = settings.daily_goal;
  const today = stats ? stats.weekly.find((day) => day.is_today) : null;
  const todayCount = stats ? (today?.count ?? 0) : null;
  const streak = stats?.streak_days ?? 0;
  const progress = active?.user_progress;
  return {
    hasActive: Boolean(active),
    canStart: Boolean(active),
    emptyHint: active ? null : "학습할 단어장을 먼저 골라 주세요.",
    vocabularyTitle: active?.title ?? null,
    progressPercent: progress ? Math.min(100, Math.max(0, Math.round(progress.progress_rate))) : 0,
    progressText: active ? `${progress.studied_words.toLocaleString(KO)} / ${active.total_words.toLocaleString(KO)} 학습` : null,
    dailyGoal: goal,
    todayCount,
    remaining: todayCount === null ? null : Math.max(0, goal - todayCount),
    goalPercent: todayCount === null ? 0 : Math.min(100, Math.round((todayCount / goal) * 100)),
    goalReached: todayCount !== null && todayCount >= goal,
    streakText: streak > 0 ? `${streak}일 연속` : null,
    studyDay: studyDay(active, stats?.day_progress, goal),
    memorizedText: active ? `암기 ${progress.memorized_words.toLocaleString(KO)} / ${active.total_words.toLocaleString(KO)}단어` : null,
  };
}

/**
 * 학습 중인 단어장의 일차 표시. 학습량은 지금 설정을 따른다.
 * @returns {null|{label: string, detail: string}} 값이 없거나 다른 단어장의 것(단어장을 막 바꾼 경우)이면 null
 */
function studyDay(active, progress, goal) {
  if (!active || !progress || progress.vocabulary_id !== active.id) return null;
  const { day, words } = progress;
  const detail = words >= goal ? `학습량을 채웠어요 (${words} / ${goal}단어). 다음 학습일에 ${day + 1}일차` : `이번 일차 ${words} / ${goal}단어`;
  return { label: `${day}일차`, detail };
}

/**
 * 세션 화면 경로. 활성 단어장 학습(all)은 source 를 생략한다.
 * @param {string} mode
 * @param {"all"|"bookmarks"|"wrong"|"due"} [source]
 */
export function startPath(mode, source = "all", options = DEFAULT_QUIZ_OPTIONS) {
  const normalized = normalizeMode(mode);
  const suffix = source === "bookmarks" || source === "wrong" || source === "due" ? `&source=${source}` : "";
  // 방향·형식은 퀴즈에만 적용하고, 기본값이면 쿼리를 늘리지 않는다
  const quiz = normalized === "quiz" ? quizQuery(options) : "";
  return `/study/session?mode=${normalized}${suffix}${quiz}`;
}

function quizQuery(options) {
  const { direction, format } = normalizeQuizOptions(options);
  return `${direction === DEFAULT_QUIZ_OPTIONS.direction ? "" : `&direction=${direction}`}${format === DEFAULT_QUIZ_OPTIONS.format ? "" : `&format=${format}`}`;
}

/** @param {unknown} value @returns {{direction: string, format: string}} 알 수 없는 값은 기본(영→한, 4지선다) */
function normalizeQuizOptions(value) {
  const raw = value && typeof value === "object" ? value : {};
  return {
    direction: DIRECTIONS.includes(raw.direction) ? raw.direction : DEFAULT_QUIZ_OPTIONS.direction,
    format: FORMATS.includes(raw.format) ? raw.format : DEFAULT_QUIZ_OPTIONS.format,
  };
}

/** @param {{getItem(key: string): string|null}|undefined} storage 마지막으로 고른 퀴즈 방향·형식. 조회 실패·깨진 값은 기본값 */
export function loadQuizOptions(storage) {
  try {
    return normalizeQuizOptions(JSON.parse(storage?.getItem(QUIZ_OPTIONS_KEY) ?? "null"));
  } catch {
    return { ...DEFAULT_QUIZ_OPTIONS };
  }
}

/** @param {{setItem(key: string, value: string): void}|undefined} storage @param {{direction: string, format: string}} options */
export function saveQuizOptions(storage, options) {
  try {
    storage?.setItem(QUIZ_OPTIONS_KEY, JSON.stringify(normalizeQuizOptions(options)));
  } catch {
    // 저장소를 못 써도 화면은 그대로 동작한다
  }
}

/** @param {{getItem(key: string): string|null}|undefined} storage @returns {"quiz"|"flashcard"} 조회 실패·깨진 값은 quiz */
export function loadMode(storage) {
  try {
    return normalizeMode(storage?.getItem(MODE_KEY));
  } catch {
    return "quiz";
  }
}

/** @param {{setItem(key: string, value: string): void}|undefined} storage @param {string} mode */
export function saveMode(storage, mode) {
  try {
    storage?.setItem(MODE_KEY, normalizeMode(mode));
  } catch {
    // 저장소를 못 써도(비공개 창 등) 화면은 그대로 동작한다
  }
}
