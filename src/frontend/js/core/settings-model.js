/*
 * 2026-11-10 - voda-voca - 학습 개수 설정 모델: 서버 응답 정규화, 폴백, 변경 적용, 모드별 문항 수 (DOM 없는 순수 로직, REQ-147)
 * 파일 위치: src/frontend/js/core/settings-model.js
 */

/** 서버를 못 받았을 때 쓰는 값. 서버 기본값·옵션과 같게 둔다 (옵션의 진짜 출처는 서버 응답). */
export const FALLBACK_SETTINGS = Object.freeze({ quiz_count: 10, flashcard_count: 10, daily_goal: 10, options: Object.freeze([10, 20, 30]) });

/** 홈 "학습 설정" 카드의 행. 순서가 화면 순서다. */
export const SETTING_ROWS = Object.freeze([
  { key: "quiz_count", label: "퀴즈" },
  { key: "flashcard_count", label: "플래시카드" },
  { key: "daily_goal", label: "오늘의 목표" },
]);

const isPositiveInt = (value) => Number.isInteger(value) && value > 0;

/**
 * 서버 응답을 화면이 믿고 쓸 수 있는 형태로 고친다. 깨진 값은 폴백으로 되돌린다.
 * @param {unknown} raw GET /api/users/me/settings 응답
 * @returns {{quiz_count: number, flashcard_count: number, daily_goal: number, options: number[]}}
 */
export function normalizeSettings(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return FALLBACK_SETTINGS;
  const options = Array.isArray(raw.options) ? raw.options.filter(isPositiveInt) : [];
  const allowed = options.length > 0 ? options : [...FALLBACK_SETTINGS.options];
  const pick = (value) => (allowed.includes(value) ? value : FALLBACK_SETTINGS.quiz_count);
  return { quiz_count: pick(raw.quiz_count), flashcard_count: pick(raw.flashcard_count), daily_goal: pick(raw.daily_goal), options: allowed };
}

/**
 * 한 항목을 바꾼 새 설정. 옵션에 없는 값·모르는 키·같은 값이면 같은 객체를 돌려준다 (변경 없음 신호).
 * @param {ReturnType<typeof normalizeSettings>} settings
 * @param {string} key
 * @param {number} value
 */
export function applySetting(settings, key, value) {
  if (!SETTING_ROWS.some((row) => row.key === key)) return settings;
  if (!settings.options.includes(value) || settings[key] === value) return settings;
  return { ...settings, [key]: value };
}

/** @param {ReturnType<typeof normalizeSettings>} settings @param {string} mode 모르는 모드는 퀴즈 */
export function sessionSizeFor(settings, mode) {
  return mode === "flashcard" ? settings.flashcard_count : settings.quiz_count;
}

/** @returns {string} 예: "20문항 학습 시작" */
export function startLabel(settings, mode) {
  return `${sessionSizeFor(settings, mode)}문항 학습 시작`;
}
