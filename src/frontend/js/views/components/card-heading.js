/*
 * 2026-11-26 - voda-voca - 카드 제목 공통 부품: 의미 색(.tone-*)을 따르는 아이콘 배지와 제목, 오른쪽 보조 요소
 * 파일 위치: src/frontend/js/views/components/card-heading.js
 */

import { h, icon } from "../../core/dom.js";

/**
 * 색은 가까운 .tone-* 조상(또는 cls 로 준 tone)을 따른다. 장식이라 아이콘은 읽어 주지 않는다.
 * @param {string} iconName Lucide 아이콘 이름
 * @param {string} [cls] 덧붙일 클래스 (예: "tone-ok")
 */
export function iconBadge(iconName, cls) {
  return h("span", { class: cls ? `icon-badge ${cls}` : "icon-badge" }, icon(iconName, "h-4 w-4"));
}

/**
 * @param {{iconName: string, title: string, level?: "h2"|"h3"|"p", aside?: Node|null}} options
 */
export function cardHeading({ iconName, title, level = "h2", aside = null }) {
  return h(
    "div",
    { class: "flex items-center justify-between gap-2" },
    h("div", { class: "flex min-w-0 items-center gap-2" }, iconBadge(iconName), h(level, { class: "min-w-0 text-base font-bold text-zinc-900" }, title)),
    aside,
  );
}
