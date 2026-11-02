/*
 * 2026-11-02 - voda-voca - 입력 필드 조립: 라벨, 입력 칸, 오류 문구를 접근성 속성과 함께 묶는다 (UI 설계서 §5, §10)
 * 파일 위치: src/frontend/js/core/form.js
 */

import { h } from "./dom.js";

export const INPUT_CLASS =
  "block w-full min-h-[44px] rounded-xl border border-zinc-300 bg-white px-3.5 py-2.5 text-base text-zinc-900 shadow-sm placeholder:text-zinc-400 transition focus:border-indigo-500 focus:outline-none focus:ring-4 focus:ring-indigo-500/15";

/**
 * @param {{id: string, label: string, type?: string, autocomplete?: string, inputmode?: string, placeholder?: string, value?: string, maxlength?: number, hint?: string}} opts
 * @returns {{wrap: HTMLElement, input: HTMLInputElement, setError: (msg: string|null) => void}}
 */
export function field({ id, label, type = "text", autocomplete, inputmode, placeholder, value = "", maxlength, hint }) {
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const input = /** @type {HTMLInputElement} */ (
    h("input", {
      id,
      name: id,
      type,
      autocomplete,
      inputmode,
      placeholder,
      maxlength,
      value,
      class: INPUT_CLASS,
      "aria-describedby": hint ? `${errorId} ${hintId}` : errorId,
    })
  );
  const error = h("p", { id: errorId, class: "hidden text-sm text-red-600", role: "alert" });
  const wrap = h(
    "div",
    { class: "space-y-1" },
    h("label", { for: id, class: "block text-sm font-medium text-zinc-700" }, label),
    input,
    hint ? h("p", { id: hintId, class: "text-xs text-zinc-500" }, hint) : null,
    error,
  );
  const setError = (msg) => {
    error.textContent = msg || "";
    error.classList.toggle("hidden", !msg);
    input.setAttribute("aria-invalid", msg ? "true" : "false");
    input.classList.toggle("border-red-500", Boolean(msg));
  };
  return { wrap, input, setError };
}

/**
 * 화면 상단의 공통 오류 배너 (role=alert). 메시지는 textContent 로 넣는다.
 * @returns {{el: HTMLElement, show: (msg: string) => void, hide: () => void}}
 */
export function alertBox() {
  const el = h("div", { role: "alert", class: "hidden rounded-xl bg-red-50 p-3 text-sm text-red-700 ring-1 ring-red-200" });
  return {
    el,
    show(msg) {
      el.textContent = msg;
      el.classList.remove("hidden");
    },
    hide() {
      el.textContent = "";
      el.classList.add("hidden");
    },
  };
}
