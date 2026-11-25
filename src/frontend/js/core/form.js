/*
 * 2026-11-02 - voda-voca - 입력 필드 조립: 라벨, 입력 칸, 오류 문구를 접근성 속성과 함께 묶는다 (UI 설계서 §5, §10)
 * 파일 위치: src/frontend/js/core/form.js
 */

import { h, icon, refreshIcons } from "./dom.js";
import { passwordToggleState } from "./password-toggle.js";

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
 * 비밀번호 입력 칸. field 와 같은 반환값에 보기/숨기기 토글(show, hide)을 더한다.
 * 토글은 입력 칸 안쪽 오른쪽에 두고(44px 터치 타깃), type="button" 이라 폼을 제출하지 않는다.
 * @param {Parameters<typeof field>[0]} opts type 은 무시한다 (항상 password 로 시작)
 * @returns {ReturnType<typeof field> & {show: () => void, hide: () => void}}
 */
export function passwordField(opts) {
  const base = field({ ...opts, type: "password" });
  let visible = false;
  const toggle = h("button", { type: "button", class: "focus-ring absolute inset-y-0 right-0 inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl text-zinc-500 hover:text-zinc-700" });

  const apply = () => {
    const state = passwordToggleState(visible);
    base.input.type = state.type;
    toggle.setAttribute("aria-label", state.label);
    toggle.setAttribute("aria-pressed", state.pressed);
    toggle.replaceChildren(icon(state.iconName));
    refreshIcons();
  };
  const set = (next) => {
    visible = next;
    apply();
  };
  toggle.addEventListener("click", () => set(!visible));

  // 입력 칸을 relative 래퍼로 감싸 토글을 겹친다. 글자가 버튼 밑으로 들어가지 않게 오른쪽 여백을 둔다.
  base.input.classList.add("pr-12");
  const holder = h("div", { class: "relative" });
  base.input.replaceWith(holder);
  holder.append(base.input, toggle);
  apply();
  return { ...base, show: () => set(true), hide: () => set(false) };
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
