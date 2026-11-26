/*
 * 2026-11-05 - voda-voca - 진행 막대: 접근성 속성을 갖춘 0~100% 게이지와 퍼센트를 곁들인 줄 (홈, 탐색, 통계 공용)
 * 파일 위치: src/frontend/js/views/components/progress-bar.js
 */

import { h } from "../../core/dom.js";

/**
 * @param {number} percent 0~100
 * @param {string} label 스크린 리더용 이름
 * @param {"progress"|"goal"|"ok"|"wrong"} [tone] 막대의 의미 색: 학습 진행(기본), 오늘 목표, 달성, 오답
 */
export function progressBar(percent, label, tone = "progress") {
  return h(
    "div",
    { class: `progress-track meter--${tone}`, role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(percent), "aria-label": label },
    h("div", { class: "progress-fill", style: `width: ${percent}%` }),
  );
}

/** 막대와 퍼센트 숫자 한 줄. 숫자는 막대의 aria-valuenow 와 같아 화면낭독기에는 한 번만 읽힌다. */
export function progressRow(percent, label, tone) {
  return h("div", { class: "meter-row" }, progressBar(percent, label, tone), h("span", { class: "meter-value", "aria-hidden": "true" }, `${percent}%`));
}
