/*
 * 2026-11-05 - voda-voca - 탐색 화면 뷰모델: 카탈로그 필터(카테고리·레벨), 선택지, 단어장 카드 표시 값 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/explore-model.js
 */

/** 서버 카테고리 코드의 표시 이름. 목록에 없는 새 카테고리는 코드를 그대로 보인다 (서버가 자유 문자열을 허용). */
export const CATEGORY_LABELS = Object.freeze({ ELEMENTARY: "초등", SECONDARY: "중고등", CSAT: "수능" });

const ALL = "all";
const KO = "ko-KR";

/** @param {unknown} value @returns {boolean} 필터를 끄는 값인가 (undefined, null, 빈 문자열, 'all') */
const isOff = (value) => value === undefined || value === null || value === "" || value === ALL;

/** @param {string} category @returns {string} */
export function categoryLabel(category) {
  return CATEGORY_LABELS[category] ?? category;
}

/**
 * 카테고리·레벨로 카탈로그를 거른다 (AND). 레벨은 select 값(문자열)으로 와도 숫자 레벨과 비교한다.
 * @param {Array<{category: string, level: number}>} catalog
 * @param {{category?: string|null, level?: string|number|null}} filter
 */
export function filterVocabularies(catalog, { category, level } = {}) {
  return catalog.filter(
    (v) => (isOff(category) || v.category === category) && (isOff(level) || v.level === Number(level)),
  );
}

/** @returns {Array<{value: string, label: string}>} 카탈로그에 실제 있는 카테고리만, 처음 나온 순서. 맨 앞에 '전체' */
export function categoryOptions(catalog) {
  const seen = [...new Set(catalog.map((v) => v.category))];
  return [{ value: ALL, label: "전체" }, ...seen.map((value) => ({ value, label: categoryLabel(value) }))];
}

/** @returns {Array<{value: string|number, label: string}>} 중복 없는 레벨 오름차순. 맨 앞에 '전체' */
export function levelOptions(catalog) {
  const levels = [...new Set(catalog.map((v) => v.level))].sort((a, b) => a - b);
  return [{ value: ALL, label: "전체" }, ...levels.map((value) => ({ value, label: `Lv.${value}` }))];
}

/**
 * 단어장 카드 한 장에 그릴 값.
 * @param {{id: number, title: string, category: string, level: number, description: string|null, total_words: number,
 *          user_progress: {studied_words: number, memorized_words: number, progress_rate: number, is_active: boolean}}} v
 */
export function vocabularyCard(v) {
  const p = v.user_progress;
  return {
    id: v.id,
    title: v.title,
    description: v.description || null,
    categoryLabel: categoryLabel(v.category),
    levelLabel: `Lv.${v.level}`,
    wordCountText: `${v.total_words.toLocaleString(KO)}단어`,
    progressPercent: Math.min(100, Math.max(0, Math.round(p.progress_rate))),
    progressText: `${p.studied_words.toLocaleString(KO)} / ${v.total_words.toLocaleString(KO)} 학습 · ${p.memorized_words.toLocaleString(KO)} 숙련`,
    isActive: p.is_active === true,
  };
}

/**
 * 카드의 버튼 위계. 화면의 주 행동(primary)은 하나여야 하므로,
 * 목록의 '선택' 은 secondary 로 낮추고 학습 중인 단어장의 '홈에서 학습' 만 primary 로 둔다.
 * @param {{isActive: boolean}} card
 * @returns {{preview: string, main: string}}
 */
export function cardActionVariants(card) {
  return { preview: "ghost", main: card.isActive ? "primary" : "secondary" };
}
