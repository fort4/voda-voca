/*
 * 2026-11-25 - voda-voca - 퀴즈 출제 옵션: 방향(영→한/한→영/섞기)과 형식(4지선다/OX) 선택 세그먼트 (VOCA-FR-023, 024)
 * 파일 위치: src/frontend/js/views/components/quiz-options.js
 */

import { h } from "../../core/dom.js";
import { DIRECTION_OPTIONS, FORMAT_OPTIONS } from "../../core/session-view-model.js";

/**
 * 라벨이 붙은 세그먼트 한 줄. 선택값은 호출자가 기억한다.
 * @param {{label: string, options: ReadonlyArray<{id: string, label: string}>, value: string, onChange: (id: string) => void}} opts
 */
function segmented({ label, options, value, onChange }) {
  const group = h("div", { class: "segmented", style: `grid-template-columns: repeat(${options.length}, minmax(0, 1fr))`, role: "group", "aria-label": label });
  const buttons = options.map((option) =>
    h(
      "button",
      {
        type: "button",
        class: "segment press focus-ring",
        onclick: () => {
          onChange(option.id);
          paint(option.id);
        },
      },
      option.label,
    ),
  );
  function paint(selected) {
    buttons.forEach((el, i) => {
      const on = options[i].id === selected;
      el.setAttribute("aria-pressed", String(on));
    });
  }
  paint(value);
  group.append(...buttons);
  return h("div", { class: "space-y-1" }, h("p", { class: "text-sm font-medium text-zinc-500" }, label), group);
}

/**
 * @param {{value: {direction: string, format: string}, onChange: (next: {direction: string, format: string}) => void}} opts
 * @returns {HTMLElement}
 */
export function renderQuizOptions({ value, onChange }) {
  let current = { ...value };
  const update = (patch) => {
    current = { ...current, ...patch };
    onChange(current);
  };
  return h(
    "div",
    { class: "space-y-3" },
    segmented({ label: "출제 방향", options: DIRECTION_OPTIONS, value: current.direction, onChange: (direction) => update({ direction }) }),
    segmented({ label: "문제 형식", options: FORMAT_OPTIONS, value: current.format, onChange: (format) => update({ format }) }),
  );
}
