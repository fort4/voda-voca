/*
 * 2026-11-02 - voda-voca - 키보드 단축키 가드: 입력 칸과 활성 모달 안에서는 단축키를 무시한다 (v1.1 Phase 1)
 * 파일 위치: src/frontend/js/core/shortcuts.js
 */

const TYPING_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

/**
 * 키 입력이 글을 쓰는 곳에서 일어났는지 본다.
 * @param {{tagName?: string, isContentEditable?: boolean}|null|undefined} el
 * @returns {boolean}
 */
export function isTypingTarget(el) {
  if (!el) return false;
  return TYPING_TAGS.has(String(el.tagName ?? "").toUpperCase()) || Boolean(el.isContentEditable);
}

/**
 * 버튼에 포커스가 있는지. Enter·Space 는 브라우저가 그 버튼을 누르므로 단축키와 겹치지 않게 뺀다.
 * @param {{tagName?: string}|null|undefined} el
 * @returns {boolean}
 */
export function isButtonTarget(el) {
  return String(el?.tagName ?? "").toUpperCase() === "BUTTON";
}

/**
 * 단축키를 막아야 하는지 판단한다. 입력 칸이거나 SweetAlert2 모달이 열려 있으면 막는다.
 * @param {{target: unknown, modalOpen: boolean}} input
 * @returns {boolean}
 */
export function shortcutsBlocked({ target, modalOpen }) {
  return Boolean(modalOpen) || isTypingTarget(target);
}

/** 활성 SweetAlert2 모달이 있는지. 모달이 없거나 라이브러리가 없으면 false. */
export function modalIsOpen() {
  try {
    return Boolean(globalThis.Swal?.isVisible?.());
  } catch {
    return false;
  }
}
