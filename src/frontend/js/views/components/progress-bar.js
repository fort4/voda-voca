/*
 * 2026-11-05 - voda-voca - 진행 막대: 접근성 속성을 갖춘 0~100% 게이지 (홈, 탐색, 통계 공용)
 * 파일 위치: src/frontend/js/views/components/progress-bar.js
 */

import { h } from "../../core/dom.js";

/** @param {number} percent 0~100 @param {string} label 스크린 리더용 이름 */
export function progressBar(percent, label) {
  return h(
    "div",
    { class: "progress-track", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(percent), "aria-label": label },
    h("div", { class: "progress-fill", style: `width: ${percent}%` }),
  );
}
