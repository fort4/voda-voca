/*
 * 2026-11-05 - voda-voca - 세션 진행 헤더: 중단(✕) 버튼, 진행 게이지, 현재/전체 문항, 읽어 주기(🔊)
 * 파일 위치: src/frontend/js/views/components/progress-header.js
 */

import { h, icon } from "../../core/dom.js";

/**
 * @param {{progress: {current: number, total: number, ratio: number}, onAbort: () => void, onSpeak: () => void}} opts
 * @returns {HTMLElement}
 */
export function renderProgressHeader({ progress, onAbort, onSpeak }) {
  const percent = Math.round(progress.ratio * 100);
  return h(
    "div",
    { class: "session-header" },
    h(
      "button",
      { type: "button", class: "press focus-ring inline-flex h-11 w-11 items-center justify-center rounded-xl", "aria-label": "학습 중단", onclick: onAbort },
      icon("x", "h-5 w-5"),
    ),
    h(
      "div",
      { class: "progress-track", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": String(progress.total), "aria-valuenow": String(progress.current), "aria-label": "학습 진행도" },
      h("div", { class: "progress-fill", style: `width: ${percent}%` }),
    ),
    h("span", { class: "progress-count" }, `${progress.current}/${progress.total}`),
    h(
      "button",
      { type: "button", class: "press focus-ring inline-flex h-11 w-11 items-center justify-center rounded-xl", "aria-label": "단어 읽어 주기", onclick: onSpeak },
      icon("volume-2", "h-5 w-5"),
    ),
  );
}
