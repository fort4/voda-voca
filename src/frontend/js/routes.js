/*
 * 2026-11-05 - voda-voca - 라우트 표: 학습 중심 화면(홈, 탐색, 학습 세션, 복습함, 통계)과 인증 화면
 * 파일 위치: src/frontend/js/routes.js
 */

/** 라우트 표를 만들 때 반드시 필요한 화면 이름. */
const REQUIRED_VIEWS = ["login", "signup", "home", "explore", "session", "review", "stats"];

/**
 * 개인 단어장·단어 편집·CSV 업로드 계열 라우트는 중앙 제공형 전환으로 폐기되어 여기에 없다.
 * 화면 함수는 app.js 가 주입한다 (이 모듈은 DOM 이나 API 에 의존하지 않는다).
 * @param {Record<string, (root: HTMLElement, ctx: object) => (void|(() => void))>} views
 * @returns {Array<{pattern: string, access: "any"|"user"|"guest", view: Function}>}
 */
export function buildRoutes(views) {
  for (const name of REQUIRED_VIEWS) {
    if (typeof views[name] !== "function") throw new Error(`라우트에 필요한 화면이 없습니다: ${name}`);
  }
  return [
    { pattern: "/", access: "user", view: views.home },
    { pattern: "/login", access: "guest", view: views.login },
    { pattern: "/signup", access: "guest", view: views.signup },
    { pattern: "/explore", access: "user", view: views.explore },
    { pattern: "/study/session", access: "user", view: views.session },
    { pattern: "/review", access: "user", view: views.review },
    { pattern: "/stats", access: "user", view: views.stats },
  ];
}
