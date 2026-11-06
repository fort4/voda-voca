/*
 * 2026-11-06 - voda-voca - 발음기호(IPA) 표시 서식: 저장값(슬래시 없는 IPA)을 /…/ 로 감싸고, 값이 없으면 null (v2.2 IPA 4단계)
 * 파일 위치: src/frontend/js/core/phonetic.js
 */

/**
 * 저장된 IPA 를 화면 서식으로 만든다. 슬래시가 섞여 들어와도 한 쌍만 남긴다.
 * @param {string|null|undefined} raw
 * @returns {string|null} 예: "/ˈæpəl/", 표시할 값이 없으면 null
 */
export function formatPhonetic(raw) {
  if (typeof raw !== "string") return null;
  const core = raw.trim().replace(/^\/+|\/+$/g, "").trim();
  return core ? `/${core}/` : null;
}

/**
 * 발음기호 요소의 속성 명세. 스크린리더는 🔊 버튼이 낭독하므로 aria-hidden 으로 이중 낭독을 막는다.
 * @param {string|null|undefined} raw
 * @returns {{class: string, "aria-hidden": string, text: string}|null} 그릴 값이 없으면 null
 */
export function phoneticSpec(raw) {
  const text = formatPhonetic(raw);
  return text ? { class: "phonetic", "aria-hidden": "true", text } : null;
}
