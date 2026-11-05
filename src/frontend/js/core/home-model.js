/*
 * 2026-11-05 - voda-voca - 홈 화면 뷰모델: 활성 단어장 요약, 오늘 목표·남은 문항, 학습 시작 경로, 마지막 모드 기억 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/home-model.js
 */

/** 하루 목표 문항 수. 서버에 목표 설정이 없어 상수로 둔다 (사용자별 목표는 후속). */
export const DAILY_GOAL = 15;
/** 한 세션의 문항 수 */
export const SESSION_SIZE = 15;

const MODE_KEY = "voda.study.mode";
const KO = "ko-KR";

/** @param {unknown} mode @returns {"quiz"|"flashcard"} 알 수 없는 값은 quiz */
const normalizeMode = (mode) => (mode === "flashcard" ? "flashcard" : "quiz");

/**
 * 홈이 그릴 값.
 * @param {{active: null|{title: string, total_words: number, user_progress: {studied_words: number, progress_rate: number}},
 *          stats: null|{streak_days: number, weekly: Array<{count: number, is_today: boolean}>}}} input
 *   stats 가 null 이면 아직 못 받은 것이다 (목표 영역은 값 없음으로 둔다).
 */
export function homeModel({ active, stats }) {
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
    todayCount,
    remaining: todayCount === null ? null : Math.max(0, DAILY_GOAL - todayCount),
    goalPercent: todayCount === null ? 0 : Math.min(100, Math.round((todayCount / DAILY_GOAL) * 100)),
    goalReached: todayCount !== null && todayCount >= DAILY_GOAL,
    streakText: streak > 0 ? `${streak}일 연속` : null,
  };
}

/**
 * 세션 화면 경로. 활성 단어장 학습(all)은 source 를 생략한다.
 * @param {string} mode
 * @param {"all"|"bookmarks"|"wrong"} [source]
 */
export function startPath(mode, source = "all") {
  const suffix = source === "bookmarks" || source === "wrong" ? `&source=${source}` : "";
  return `/study/session?mode=${normalizeMode(mode)}${suffix}`;
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
