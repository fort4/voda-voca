/*
 * 2026-11-05 - voda-voca - 하단 탭 내비게이션 규칙: 탭 정의, 활성 탭 판정, 탭바 표시 조건 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/nav.js
 */

/** 앱의 첫 화면 경로. 로그인 직후와 브랜드 로고가 향하는 곳이다. */
export const HOME_PATH = "/";

/**
 * 하단 탭. 한 손으로 누르는 1-Depth 이동이며 순서가 곧 화면 순서다.
 * prefix 는 활성 탭을 가리는 경로 접두사다 (홈은 '/' 정확히 일치).
 * @type {ReadonlyArray<{id: string, href: string, label: string, iconName: string, prefix: string}>}
 */
export const TABS = Object.freeze([
  { id: "home", href: "#/", label: "홈", iconName: "home", prefix: "/" },
  { id: "explore", href: "#/explore", label: "탐색", iconName: "search", prefix: "/explore" },
  { id: "review", href: "#/review", label: "복습함", iconName: "star", prefix: "/review" },
  { id: "stats", href: "#/stats", label: "통계", iconName: "bar-chart-3", prefix: "/stats" },
]);

/** 탭바를 숨기는 경로. 인증 화면과, 한 문항에만 집중해야 하는 학습 세션이다. */
const HIDDEN_PATHS = ["/login", "/signup", "/study/session"];

/** @param {string} path @param {string} base @returns {boolean} base 이거나 그 하위 경로인가 */
function isUnder(path, base) {
  return path === base || path.startsWith(`${base}/`);
}

/** @param {string} path @returns {string} 끝의 슬래시를 뗀 경로 ('/' 는 그대로) */
function trimmed(path) {
  return path.length > 1 ? path.replace(/\/+$/, "") : path;
}

/**
 * 경로에 해당하는 탭 id. 어느 탭에도 속하지 않으면 null.
 * @param {string} path
 * @returns {string|null}
 */
export function activeTabId(path) {
  const clean = trimmed(path || "");
  if (!clean) return null;
  const tab = TABS.find((item) => (item.prefix === HOME_PATH ? clean === HOME_PATH : isUnder(clean, item.prefix)));
  return tab ? tab.id : null;
}

/**
 * 탭바를 보일지. 로그인 상태이고 인증 화면·학습 세션이 아닐 때만 보인다.
 * @param {string} path
 * @param {unknown} user
 * @returns {boolean}
 */
export function isTabbarVisible(path, user) {
  if (!user) return false;
  const clean = trimmed(path || "");
  return !HIDDEN_PATHS.some((hidden) => isUnder(clean, hidden));
}
