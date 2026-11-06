/*
 * 2026-11-06 - voda-voca - 발음기호 요소 컴포넌트: 해설 시트·플래시카드 뒷면·단어 시트가 공유한다 (값이 없으면 null)
 * 파일 위치: src/frontend/js/views/components/phonetic-line.js
 */

import { h } from "../../core/dom.js";
import { phoneticSpec } from "../../core/phonetic.js";

/**
 * @param {string|null|undefined} raw 저장된 IPA (슬래시 없음)
 * @returns {HTMLElement|null} 값이 없으면 null (레이아웃에 빈 줄을 만들지 않는다)
 */
export function phoneticLine(raw) {
  const spec = phoneticSpec(raw);
  if (!spec) return null;
  return h("span", { class: spec.class, "aria-hidden": spec["aria-hidden"] }, spec.text);
}
