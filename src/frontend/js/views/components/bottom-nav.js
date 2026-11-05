/*
 * 2026-11-05 - voda-voca - 하단 탭 내비게이션 컴포넌트: 4개 탭을 그리고 현재 경로의 탭을 표시한다
 * 파일 위치: src/frontend/js/views/components/bottom-nav.js
 */

import { clear, h, icon, refreshIcons } from "../../core/dom.js";
import { TABS, activeTabId, isTabbarVisible } from "../../core/nav.js";

/**
 * 탭바를 다시 그린다. 보일 조건(로그인, 인증 화면·학습 세션 제외)은 core/nav.js 의 규칙을 따른다.
 * 색은 css/app.css 의 .tab-link 가 라이트·다크 모두 정의한다.
 * @param {HTMLElement} container 탭바를 담는 <nav>
 * @param {{path: string, user: unknown}} state
 */
export function renderBottomNav(container, { path, user }) {
  clear(container);
  if (!isTabbarVisible(path, user)) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  const active = activeTabId(path);
  container.append(
    h(
      "div",
      { class: "mx-auto grid max-w-screen-md grid-cols-4" },
      TABS.map((tab) =>
        h(
          "a",
          {
            href: tab.href,
            class: "tab-link focus-ring flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-micro font-semibold tracking-tight",
            "aria-current": tab.id === active ? "page" : null,
          },
          h("span", { class: "tab-pill" }, icon(tab.iconName, "h-5 w-5")),
          tab.label,
        ),
      ),
    ),
  );
  refreshIcons();
}
