/*
 * 2026-11-02 - voda-voca - 앱 상태: 로그인 사용자 정보를 메모리에만 보관 (세션 쿠키는 JS 에서 읽지 않음, REQ-001)
 * 파일 위치: src/frontend/js/core/state.js
 */

/** @type {{user: null | {id: number, email: string, nickname: string}}} */
const state = { user: null };

/** @returns {typeof state.user} */
export function getUser() {
  return state.user;
}

/** @param {typeof state.user} user */
export function setUser(user) {
  state.user = user ?? null;
}
