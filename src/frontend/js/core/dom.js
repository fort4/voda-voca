/*
 * 2026-11-02 - voda-voca - DOM 헬퍼: 텍스트는 항상 textContent 로 넣어 XSS 를 막는다. innerHTML 은 쓰지 않는다 (REQ-111, REQ-020)
 * 파일 위치: src/frontend/js/core/dom.js
 */

/**
 * 요소를 만든다. 문자열 자식은 텍스트 노드로 넣어 HTML 로 해석되지 않는다.
 * @param {string} tag
 * @param {Record<string, unknown>} [props] class, on<이벤트>, dataset, 그 밖의 속성
 * @param {...(Node|string|number|false|null|undefined|Array)} children
 * @returns {HTMLElement}
 */
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props ?? {})) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") {
      el.className = String(value);
    } else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "dataset" && typeof value === "object") {
      Object.assign(el.dataset, value);
    } else {
      el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  appendChildren(el, children);
  return el;
}

/**
 * @param {HTMLElement} el
 * @param {Array<unknown>} children
 */
export function appendChildren(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

/** @param {HTMLElement} el */
export function clear(el) {
  el.replaceChildren();
}

/**
 * Lucide 아이콘 자리 표시자. refreshIcons() 가 SVG 로 바꾼다.
 * @param {string} name Lucide 아이콘 이름 (예: "arrow-left")
 * @param {string} [cls]
 * @returns {HTMLElement}
 */
export function icon(name, cls = "h-5 w-5") {
  return h("i", { "data-lucide": name, class: cls, "aria-hidden": "true" });
}

/** 현재 DOM 의 data-lucide 요소를 SVG 로 바꾼다. Lucide 가 로드되지 않았으면 아무 일도 하지 않는다. */
export function refreshIcons() {
  if (globalThis.lucide?.createIcons) globalThis.lucide.createIcons();
}

/**
 * 로딩 중 자리 표시 블록 (스켈레톤). 실제 카드와 비슷한 높이를 가져 화면이 튀지 않게 한다 (UI 설계서 §4).
 * @param {number} count
 * @returns {HTMLElement}
 */
export function skeleton(count = 3) {
  return h(
    "div",
    { class: "space-y-3", "aria-busy": "true" },
    h("span", { class: "sr-only" }, "불러오는 중"),
    Array.from({ length: count }, () => h("div", { class: "h-20 animate-pulse rounded-xl bg-slate-200" })),
  );
}

/**
 * 상태 메시지 블록 (Empty, Error 공통 틀). 행동 버튼은 선택.
 * @param {{iconName: string, title: string, text?: string, action?: HTMLElement}} opts
 * @returns {HTMLElement}
 */
export function notice({ iconName, title, text, action }) {
  return h(
    "section",
    { class: "flex flex-col items-center gap-3 rounded-xl bg-white px-6 py-10 text-center shadow-sm" },
    h("div", { class: "text-slate-400" }, icon(iconName, "h-10 w-10")),
    h("p", { class: "text-lg font-semibold text-slate-800" }, title),
    text ? h("p", { class: "text-sm text-slate-600" }, text) : null,
    action ?? null,
  );
}

/**
 * 최소 44×44px 버튼. variant: primary | secondary | danger | ghost
 * @param {{variant?: string, type?: string, onClick?: (e: Event) => void, disabled?: boolean, full?: boolean}} opts
 * @param {...any} children
 * @returns {HTMLButtonElement}
 */
export function button({ variant = "primary", type = "button", onClick, disabled = false, full = false }, ...children) {
  const variants = {
    primary: "bg-blue-600 text-white hover:bg-blue-700",
    secondary: "bg-white text-slate-800 ring-1 ring-slate-300 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
    ghost: "text-slate-700 hover:bg-slate-100",
  };
  return /** @type {HTMLButtonElement} */ (
    h(
      "button",
      {
        type,
        class: `inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-xl px-4 font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant] ?? variants.primary} ${full ? "w-full" : ""}`,
        onclick: onClick,
        disabled,
      },
      ...children,
    )
  );
}
