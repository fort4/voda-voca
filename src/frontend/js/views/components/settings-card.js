/*
 * 2026-11-10 - voda-voca - 학습 설정 카드: 퀴즈·플래시카드 문항 수와 오늘의 목표를 10/20/30 칩으로 고른다 (REQ-147)
 * 파일 위치: src/frontend/js/views/components/settings-card.js
 */

import { h } from "../../core/dom.js";
import { SETTING_ROWS } from "../../core/settings-model.js";

/**
 * @param {{settings: {quiz_count: number, flashcard_count: number, daily_goal: number, options: number[]},
 *          onChange: (key: string, value: number) => void}} opts
 * @returns {HTMLElement}
 */
export function renderSettingsCard({ settings, onChange }) {
  return h(
    "section",
    { class: "card rise-in space-y-3", "aria-label": "학습 설정" },
    h("p", { class: "text-sm font-medium text-zinc-500" }, "학습 설정 (문항 수)"),
    ...SETTING_ROWS.map((row) =>
      h(
        "div",
        { class: "flex items-center justify-between gap-3", role: "group", "aria-label": row.label },
        h("span", { class: "text-body font-semibold text-zinc-900" }, row.label),
        h(
          "div",
          { class: "grid flex-1 max-w-[15rem] gap-2", style: `grid-template-columns: repeat(${settings.options.length}, minmax(0, 1fr))` },
          ...settings.options.map((value) =>
            h(
              "button",
              {
                type: "button",
                class: "chip focus-ring min-h-[44px] w-full",
                "aria-pressed": String(settings[row.key] === value),
                "data-setting": `${row.key}:${value}`,
                onclick: () => onChange(row.key, value),
              },
              String(value),
            ),
          ),
        ),
      ),
    ),
  );
}
