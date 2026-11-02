/*
 * 2026-11-02 - voda-voca - 메뉴 팝오버: 앵커 버튼 아래에 아이콘과 글자가 있는 메뉴를 띄운다. 바깥 클릭과 ESC 로 닫힌다. 한 번에 하나만 연다.
 * 파일 위치: src/frontend/js/core/popover.js
 */

import { h, icon, refreshIcons } from "./dom.js";

/** @type {(() => void) | null} 지금 열린 팝오버를 닫는 함수 */
let activeClose = null;

/**
 * @typedef {{key: string, label: string, icon: string, danger?: boolean}} MenuItem
 */

/**
 * 메뉴 항목 모양을 만든다. 순수 함수 아님: DOM 을 만든다.
 * @param {MenuItem} item
 * @param {() => void} onSelect
 */
function menuButton(item, onSelect) {
  return h(
    "button",
    {
      type: "button",
      role: "menuitem",
      class: item.danger ? "dropdown-item dropdown-item--danger" : "dropdown-item",
      onclick: onSelect,
    },
    icon(item.icon, "h-5 w-5"),
    h("span", {}, item.label),
  );
}

/**
 * 앵커 아래에 메뉴를 띄운다.
 * @param {HTMLElement} anchor 메뉴를 여는 버튼
 * @param {MenuItem[]} items
 * @param {(key: string) => void} onSelect 항목을 고르면 메뉴를 먼저 닫고 호출한다
 * @param {{label: string}} opts 접근성 이름
 * @returns {() => void} 닫는 함수
 */
export function openMenuPopover(anchor, items, onSelect, { label }) {
  if (activeClose) activeClose();

  const close = () => {
    document.removeEventListener("keydown", onKey);
    backdrop.remove();
    popover.remove();
    anchor.setAttribute("aria-expanded", "false");
    if (activeClose === close) activeClose = null;
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };

  const backdrop = h("div", { class: "dropdown-backdrop", onclick: close });
  const popover = h(
    "div",
    { class: "dropdown-popover", role: "menu", "aria-label": label },
    ...items.map((item, index) => {
      const button = menuButton(item, () => {
        close();
        onSelect(item.key);
      });
      return index > 0 && item.danger ? [h("div", { class: "dropdown-divider" }), button] : button;
    }).flat(),
  );

  const rect = anchor.getBoundingClientRect();
  popover.style.top = `${rect.bottom + 6}px`;
  popover.style.right = `${Math.max(8, window.innerWidth - rect.right)}px`;
  document.body.append(backdrop, popover);
  anchor.setAttribute("aria-expanded", "true");
  document.addEventListener("keydown", onKey);
  activeClose = close;
  refreshIcons();
  popover.querySelector("button")?.focus();
  return close;
}
