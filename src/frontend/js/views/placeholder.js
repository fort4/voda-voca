/*
 * 2026-11-05 - voda-voca - 준비 중 화면: 라우트와 내비게이션을 먼저 연결해 두고, 각 화면은 이후 단계에서 실제 구현으로 바꾼다
 * 파일 위치: src/frontend/js/views/placeholder.js
 */

import { notice } from "../core/dom.js";

/**
 * @param {{iconName: string, title: string, text: string}} opts
 * @returns {(root: HTMLElement) => void}
 */
export function placeholderView({ iconName, title, text }) {
  return (root) => {
    root.append(notice({ iconName, title, text }));
  };
}
