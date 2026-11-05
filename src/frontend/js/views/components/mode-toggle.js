/*
 * 2026-11-05 - voda-voca - 학습 모드 토글: 퀴즈 / 플래시카드 두 칸 선택 (선택값은 호출자가 기억한다)
 * 파일 위치: src/frontend/js/views/components/mode-toggle.js
 */

import { h } from "../../core/dom.js";

const MODES = [
  { id: "quiz", label: "퀴즈" },
  { id: "flashcard", label: "플래시카드" },
];

/**
 * @param {{value: "quiz"|"flashcard", onChange: (mode: "quiz"|"flashcard") => void}} opts
 * @returns {HTMLElement}
 */
export function renderModeToggle({ value, onChange }) {
  const group = h("div", { class: "grid grid-cols-2 gap-1 rounded-xl bg-zinc-100 p-1", role: "group", "aria-label": "학습 방식" });
  const buttons = MODES.map((mode) =>
    h(
      "button",
      {
        type: "button",
        class: "press focus-ring min-h-[44px] rounded-lg px-3 text-body font-semibold",
        "aria-pressed": String(mode.id === value),
        onclick: () => {
          onChange(mode.id);
          paint(mode.id);
        },
      },
      mode.label,
    ),
  );
  function paint(selected) {
    buttons.forEach((el, i) => {
      const on = MODES[i].id === selected;
      el.setAttribute("aria-pressed", String(on));
      el.className = `press focus-ring min-h-[44px] rounded-lg px-3 text-body font-semibold ${on ? "bg-white text-indigo-600 shadow-sm" : "text-zinc-600"}`;
    });
  }
  paint(value);
  group.append(...buttons);
  return group;
}
