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

/**
 * 아이콘 자리표시자(<i data-lucide="…">)를 SVG 로 바꾼다.
 * 화면과 모달이 새로 그려질 때마다 호출한다 (라우터 afterRender, 모달 didOpen).
 * Lucide 가 로드되지 않았으면 아무 일도 하지 않는다. 예외를 던지지 않는다.
 * @returns {boolean} 실제로 변환을 시도했는지
 */
export function refreshIcons() {
  const lib = globalThis.lucide;
  if (!lib || typeof lib.createIcons !== "function") return false;
  lib.createIcons();
  return true;
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
    Array.from({ length: count }, () => h("div", { class: "h-20 animate-pulse rounded-xl bg-zinc-200" })),
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
    { class: "surface rise-in flex flex-col items-center gap-3 px-6 py-10 text-center" },
    h("div", { class: "grid h-14 w-14 place-items-center rounded-2xl bg-zinc-100 text-zinc-500" }, icon(iconName, "h-7 w-7")),
    h("p", { class: "text-lg font-semibold tracking-tight text-zinc-900" }, title),
    text ? h("p", { class: "text-sm text-zinc-600" }, text) : null,
    action ?? null,
  );
}

/**
 * 버튼. 최소 44×44px 터치 타깃, 누르면 살짝 눌리는 마이크로 인터랙션, 키보드 포커스 링 (디자인 시스템: app.css).
 * variant: primary(인디고 채움) | secondary(표면 + 보더) | danger(빨강 채움) | ghost(글자만)
 * @param {{variant?: string, type?: string, onClick?: (e: Event) => void, disabled?: boolean, full?: boolean}} opts
 * @param {...any} children
 * @returns {HTMLButtonElement}
 */
export function button({ variant = "primary", type = "button", onClick, disabled = false, full = false, ...rest }, ...children) {
  const variants = {
    primary: "bg-indigo-600 text-white shadow-sm hover:bg-indigo-700",
    secondary: "surface text-zinc-800 hover:bg-zinc-50",
    danger: "bg-red-600 text-white shadow-sm hover:bg-red-700",
    ghost: "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900",
    "danger-soft": "bg-red-50 text-red-700 ring-1 ring-red-200 hover:bg-red-100",
  };
  return /** @type {HTMLButtonElement} */ (
    h(
      "button",
      {
        type,
        class: `press focus-ring inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-xl px-4 text-[15px] font-semibold tracking-tight transition disabled:cursor-not-allowed disabled:opacity-50 ${variants[variant] ?? variants.primary} ${full ? "w-full" : ""}`,
        onclick: onClick,
        disabled,
        ...rest,
      },
      ...children,
    )
  );
}
