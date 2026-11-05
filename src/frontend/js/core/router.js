/*
 * 2026-11-02 - voda-voca - 해시 라우터: 경로 파싱, 패턴 매칭, 인증 가드, 안전한 next 경로 검사 (REQ-001, REQ-021)
 * 파일 위치: src/frontend/js/core/router.js
 */

/**
 * "#/login?next=%2Fexplore" → {path: "/login", query: {next: "/explore"}}
 * @param {string} hash
 * @returns {{path: string, query: Record<string, string>}}
 */
export function parseHash(hash) {
  const raw = (hash || "").replace(/^#/, "") || "/";
  const [pathPart, queryPart = ""] = raw.split("?");
  let path = pathPart.startsWith("/") ? pathPart : `/${pathPart}`;
  if (path.length > 1) path = path.replace(/\/+$/, "");
  return { path, query: Object.fromEntries(new URLSearchParams(queryPart)) };
}

/**
 * 패턴과 실제 경로를 맞춘다. ":name" 은 한 구간을 받아 params 에 담는다.
 * @param {Array<{pattern: string, view: unknown, access: string}>} routes
 * @param {string} path
 * @returns {{route: any, params: Record<string, string>}|null}
 */
export function matchRoute(routes, path) {
  const parts = path.split("/").filter(Boolean);
  for (const route of routes) {
    const patternParts = route.pattern.split("/").filter(Boolean);
    if (patternParts.length !== parts.length) continue;
    const params = {};
    let ok = true;
    for (let i = 0; i < patternParts.length; i += 1) {
      const p = patternParts[i];
      if (p.startsWith(":")) {
        params[p.slice(1)] = decodeURIComponent(parts[i]);
      } else if (p !== parts[i]) {
        ok = false;
        break;
      }
    }
    if (ok) return { route, params };
  }
  return null;
}

/**
 * 로그인 후 돌아갈 경로를 검사한다. 같은 앱의 경로(#/로 시작하는 해시 경로)만 허용하고, 그 밖은 기본값으로 바꾼다.
 * 열린 리다이렉트를 막는다.
 * @param {unknown} value
 * @param {string} [fallback]
 * @returns {string}
 */
export function safeNext(value, fallback = "/") {
  if (typeof value !== "string") return fallback;
  if (!value.startsWith("/") || value.startsWith("//")) return fallback;
  if (/[:\\\s]/.test(value.split("?")[0])) return fallback;
  return value;
}

/**
 * @typedef {{pattern: string, access: "any"|"user"|"guest", view: (root: HTMLElement, ctx: object) => (void|(() => void))}} Route
 */

/**
 * 라우터를 만든다. 경로가 바뀔 때마다 이전 화면의 정리 함수를 부르고 새 화면을 그린다.
 * @param {{routes: Route[], root: HTMLElement, getUser: () => unknown, onNotFound?: () => void}} opts
 */
export function createRouter({ routes, root, getUser, onNotFound, afterRender = () => {} }) {
  let cleanup = null;

  /** @param {string} path @param {Record<string, string>} query */
  function toHash(path, query = {}) {
    const qs = new URLSearchParams(query).toString();
    return `#${path}${qs ? `?${qs}` : ""}`;
  }

  /** @param {string} path @param {Record<string, string>} [query] */
  function navigate(path, query = {}) {
    const target = toHash(path, query);
    if (location.hash === target) {
      render(); // 같은 경로면 hashchange 가 나지 않으므로 직접 다시 그린다
    } else {
      location.hash = target;
    }
  }

  /** @param {string} path @param {Record<string, string>} [query] */
  function replace(path, query = {}) {
    location.replace(toHash(path, query));
  }

  function render() {
    if (typeof cleanup === "function") cleanup();
    cleanup = null;
    root.replaceChildren();

    const { path, query } = parseHash(location.hash);
    const match = matchRoute(routes, path);
    if (!match) {
      if (onNotFound) onNotFound();
      return;
    }
    const user = getUser();
    const { route, params } = match;
    if (route.access === "user" && !user) {
      replace("/login", { next: path + (Object.keys(query).length ? `?${new URLSearchParams(query)}` : "") });
      return;
    }
    if (route.access === "guest" && user) {
      replace("/");
      return;
    }
    const result = route.view(root, { params, query, path, navigate, replace });
    if (typeof result === "function") cleanup = result;
    afterRender();
  }

  function start() {
    window.addEventListener("hashchange", render);
    render();
  }

  return { start, render, navigate, replace };
}
