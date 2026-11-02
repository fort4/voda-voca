/*
 * 2026-11-02 - voda-voca - 다크 모드 테마 관리자: 저장값 > 시스템 설정 순으로 초기 판정, .dark 클래스 적용, 사용자가 바꾸면 저장 (v1.1 Phase 1)
 * 파일 위치: src/frontend/js/core/theme.js
 */

export const THEME_KEY = "voda.theme";
export const THEMES = Object.freeze(["light", "dark"]);
const DARK_QUERY = "(prefers-color-scheme: dark)";

/**
 * 초기 테마를 정한다. 저장된 값이 light 또는 dark 면 그것을 쓰고, 아니면 시스템 설정을 따른다.
 * @param {{stored: unknown, prefersDark: boolean}} input
 * @returns {"light"|"dark"}
 */
export function resolveInitialTheme({ stored, prefersDark }) {
  if (stored === "dark" || stored === "light") return stored;
  return prefersDark ? "dark" : "light";
}

/**
 * 테마 관리자. 저장소, 루트 요소, matchMedia 를 주입받는다 (테스트 가능).
 * @param {{storage?: Storage|null, root?: HTMLElement|{classList: {toggle(name: string, on?: boolean): void, contains(name: string): boolean}}, matchMedia?: (q: string) => {matches: boolean}}} [deps]
 */
export function createThemeManager({
  storage = globalThis.localStorage,
  root = globalThis.document?.documentElement,
  matchMedia = globalThis.matchMedia,
} = {}) {
  const readStored = () => {
    try {
      return storage ? storage.getItem(THEME_KEY) : null;
    } catch {
      return null; // 저장소를 쓸 수 없으면 시스템 설정으로 판단한다
    }
  };
  const writeStored = (theme) => {
    try {
      storage?.setItem(THEME_KEY, theme);
    } catch {
      // 저장 실패는 화면 전환을 막지 않는다
    }
  };
  const prefersDark = () => {
    try {
      return Boolean(matchMedia?.(DARK_QUERY)?.matches);
    } catch {
      return false;
    }
  };

  let current = resolveInitialTheme({ stored: readStored(), prefersDark: prefersDark() });
  apply(current);

  function apply(theme) {
    root?.classList?.toggle("dark", theme === "dark");
  }

  return {
    current: () => current,
    /** 현재 테마를 그대로 두고 화면에만 반영한다 (초기화용). */
    apply() {
      apply(current);
    },
    /**
     * 사용자가 테마를 바꾼다. 선택은 저장하므로 다음 방문에도 유지된다.
     * @returns {"light"|"dark"} 바뀐 테마
     */
    toggle() {
      current = current === "dark" ? "light" : "dark";
      apply(current);
      writeStored(current);
      return current;
    },
  };
}
