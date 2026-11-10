/*
 * 2026-11-10 - voda-voca - 품사 태그 컴포넌트: 퀴즈 문제·플래시카드 앞면·해설 시트·단어 시트가 공유한다 (값이 없으면 null)
 * 파일 위치: src/frontend/js/views/components/pos-tag.js
 */

import { h } from "../../core/dom.js";
import { posSpec } from "../../core/pos.js";

/**
 * @param {string|null|undefined} raw 서버의 품사 (예: "noun")
 * @returns {HTMLElement|null} 값이 없으면 null (빈 칸을 만들지 않는다)
 */
export function posTag(raw) {
  const spec = posSpec(raw);
  return spec ? h("span", { class: spec.class }, spec.text) : null;
}
