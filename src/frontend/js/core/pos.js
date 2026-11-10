/*
 * 2026-11-10 - voda-voca - 품사 표시: 서버의 영문 소문자 품사를 한글 라벨로 바꾼다 (v2.2 품사 노출)
 * 파일 위치: src/frontend/js/core/pos.js
 */

/** 시드가 쓰는 품사 8종의 한글 라벨. 목록에 없는 값은 그대로 보인다. */
export const POS_LABELS = Object.freeze({
  noun: "명사",
  verb: "동사",
  adjective: "형용사",
  adverb: "부사",
  preposition: "전치사",
  conjunction: "접속사",
  pronoun: "대명사",
  interjection: "감탄사",
});

/**
 * @param {string|null|undefined} raw 서버의 품사 (예: "noun")
 * @returns {string|null} 한글 라벨, 값이 없으면 null
 */
export function posLabel(raw) {
  if (typeof raw !== "string") return null;
  const key = raw.trim().toLowerCase();
  if (!key) return null;
  return POS_LABELS[key] ?? raw.trim();
}

/**
 * 품사 요소의 속성 명세. 낭독해도 자연스러운 한글이라 aria-hidden 은 쓰지 않는다.
 * @param {string|null|undefined} raw
 * @returns {{class: string, text: string}|null} 그릴 값이 없으면 null
 */
export function posSpec(raw) {
  const text = posLabel(raw);
  return text ? { class: "pos-tag", text } : null;
}
