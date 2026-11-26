/*
 * 2026-11-26 - voda-voca - 통계 탭 안의 전환: 내 통계 / 순위 (REQ-172)
 * 파일 위치: src/frontend/js/views/components/stats-switch.js
 */

import { h } from "../../core/dom.js";

const SECTIONS = [
  { id: "stats", href: "#/stats", label: "내 통계" },
  { id: "ranking", href: "#/stats/ranking", label: "순위" },
];

/**
 * 두 화면은 주소가 달라 링크다. 지금 화면은 aria-current 로 알린다.
 * @param {"stats"|"ranking"} current
 * @returns {HTMLElement}
 */
export function statsSwitch(current) {
  return h(
    "nav",
    { class: "segmented mb-4 grid-cols-2", "aria-label": "통계 보기" },
    SECTIONS.map((section) =>
      h(
        "a",
        { href: section.href, class: "segment press focus-ring grid place-items-center", "aria-current": section.id === current ? "page" : null },
        section.label,
      ),
    ),
  );
}
