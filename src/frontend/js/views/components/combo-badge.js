/*
 * 2026-11-05 - voda-voca - 콤보 뱃지 줄: 진행 헤더 아래 고정 높이 줄에 'N콤보' 뱃지를 그린다 (2콤보부터, 증가 때만 바운스) (v2.2)
 * 파일 위치: src/frontend/js/views/components/combo-badge.js
 */

import { h, icon } from "../../core/dom.js";

/**
 * 뱃지 클래스. 계산은 combo-model.js 의 badgeView 결과를 그대로 따른다.
 * @param {{bounce: boolean, milestone: boolean}} view
 * @returns {string}
 */
export function comboBadgeClass(view) {
  return `combo-badge${view.milestone ? " combo-badge--milestone" : ""}${view.bounce ? " is-bounce" : ""}`;
}

/**
 * 뱃지 줄. 뱃지가 없어도 줄의 높이는 그대로라서 나타나고 사라질 때 아래 카드가 밀리지 않는다.
 * 해설 시트가 같은 정보를 이미 읽어 주므로 시각 전용(aria-hidden)이다.
 * @param {{visible: boolean, bounce: boolean, milestone: boolean, label: string}} view
 * @returns {HTMLElement}
 */
export function renderComboRow(view) {
  return h(
    "div",
    { class: "combo-row", "aria-hidden": "true" },
    view.visible ? h("span", { class: comboBadgeClass(view) }, icon("flame", "h-4 w-4"), view.label) : null,
  );
}
