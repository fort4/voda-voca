/*
 * 2026-11-02 - voda-voca - 앱 진입점: 세션 확인(/auth/me), 라우트 등록, 상단바, 세션 만료 처리 (REQ-001, REQ-002)
 * 파일 위치: src/frontend/js/app.js
 */

import { api, setUnauthorizedHandler } from "./core/api.js";
import { nicknameConfirmationMatches } from "./core/validate.js";
import { button, clear, h, notice, refreshIcons, icon } from "./core/dom.js";
import { createRouter, parseHash, safeNext } from "./core/router.js";
import { getUser, setUser } from "./core/state.js";
import { confirmDialog, toast } from "./core/toast.js";
import { loginView } from "./views/login.js";
import { signupView } from "./views/signup.js";
import { wordbooksView } from "./views/wordbooks.js";
import { wordsView } from "./views/words.js";
import { flashcardsView } from "./views/flashcards.js";
import { quizView } from "./views/quiz.js";
import { bookmarksView } from "./views/bookmarks.js";
import { historyView } from "./views/history.js";
import { clearQuizResults } from "./core/result-cache.js";

const root = /** @type {HTMLElement} */ (document.getElementById("app"));
const userbar = /** @type {HTMLElement} */ (document.getElementById("userbar"));
const tabbar = /** @type {HTMLElement} */ (document.getElementById("tabbar"));

const TABS = [
  { href: "#/wordbooks", label: "단어장", iconName: "book-open", prefix: "/wordbooks" },
  { href: "#/bookmarks", label: "북마크", iconName: "star", prefix: "/bookmarks" },
  { href: "#/history", label: "이력", iconName: "history", prefix: "/history" },
];

/** 하단 탭바: 로그인 상태에서만 보이고, 현재 경로에 해당하는 탭을 표시한다 (2단계 네비게이션). */
function renderTabbar() {
  clear(tabbar);
  if (!getUser()) {
    tabbar.hidden = true;
    return;
  }
  tabbar.hidden = false;
  const current = parseHash(location.hash).path;
  tabbar.append(
    h(
      "div",
      { class: "mx-auto grid max-w-screen-md grid-cols-3" },
      TABS.map((tab) => {
        const active = current === tab.prefix || current.startsWith(`${tab.prefix}/`);
        return h(
          "a",
          {
            href: tab.href,
            class: "tab-link focus-ring flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-[11px] font-semibold tracking-tight",
            "aria-current": active ? "page" : null,
          },
          h("span", { class: "tab-pill" }, icon(tab.iconName, "h-5 w-5")),
          tab.label,
        );
      }),
    ),
  );
  refreshIcons();
}

/** 상단바: 로그인 상태에 따라 계정 메뉴(닉네임 칩), 또는 로그인 링크를 보인다. */
function renderUserbar() {
  clear(userbar);
  const user = getUser();
  if (user) {
    userbar.append(
      button(
        { variant: "ghost", onClick: openAccountMenu, "aria-label": `${user.nickname} 계정 메뉴` },
        h("span", { class: "grid h-7 w-7 place-items-center rounded-full bg-indigo-600 text-xs font-bold text-white" }, initialOf(user.nickname)),
        h("span", { class: "hidden max-w-[9rem] truncate text-sm font-medium text-zinc-700 sm:inline" }, user.nickname),
        icon("chevron-down", "h-4 w-4 text-zinc-400"),
      ),
    );
  } else {
    userbar.append(
      h("a", { href: "#/login", class: "focus-ring inline-flex min-h-[44px] items-center rounded-xl px-3 text-sm font-semibold text-indigo-600 hover:bg-indigo-50" }, "로그인"),
    );
  }
}

/** @param {string} nickname @returns {string} 아바타에 쓸 첫 글자 (코드 포인트 기준) */
function initialOf(nickname) {
  return Array.from(nickname)[0]?.toUpperCase() ?? "?";
}

/**
 * 계정 메뉴: 로그아웃과 회원 탈퇴. 탈퇴는 별도의 위험 동작이라 아래 흐름으로만 진행한다.
 */
async function openAccountMenu() {
  const user = getUser();
  if (!user || !globalThis.Swal) return;
  const result = await globalThis.Swal.fire({
    title: user.nickname,
    text: "계정 메뉴입니다.",
    showCancelButton: true,
    showDenyButton: true,
    confirmButtonText: "로그아웃",
    denyButtonText: "회원 탈퇴",
    cancelButtonText: "닫기",
    confirmButtonColor: "#4f46e5",
    denyButtonColor: "#dc2626",
    reverseButtons: true,
  });
  if (result.isConfirmed) await logout();
  else if (result.isDenied) await withdraw();
}

async function logout() {
  try {
    await api("/auth/logout", { method: "POST", skipAuthRedirect: true });
  } catch {
    // 세션이 이미 없어도 로컬 상태는 지운다
  }
  setUser(null);
  clearQuizResults(globalThis.sessionStorage);
  renderUserbar();
  renderTabbar();
  router.navigate("/login");
}

/**
 * 회원 탈퇴. 두 번 확인한다: 경고 확인, 그리고 닉네임을 직접 입력하는 최종 확인.
 * 성공하면 세션 저장소를 비우고 로그인 화면으로 간다.
 */
async function withdraw() {
  const user = getUser();
  if (!user || !globalThis.Swal) return;
  const first = await confirmDialog({
    title: "회원 탈퇴를 진행할까요?",
    text: "계정과 모든 단어장, 단어, 북마크, 학습 기록이 영구 삭제됩니다. 되돌릴 수 없습니다.",
    confirmText: "계속",
    danger: true,
  });
  if (!first) return;

  const final = await globalThis.Swal.fire({
    title: "최종 확인",
    text: `확인하려면 닉네임 '${user.nickname}'을(를) 정확히 입력하세요.`,
    input: "text",
    inputPlaceholder: user.nickname,
    inputAttributes: { autocomplete: "off", "aria-label": "닉네임 확인" },
    showCancelButton: true,
    confirmButtonText: "탈퇴하기",
    cancelButtonText: "취소",
    confirmButtonColor: "#dc2626",
    inputValidator: (value) => (nicknameConfirmationMatches(value, user.nickname) ? null : "닉네임이 일치하지 않습니다."),
  });
  if (!final.isConfirmed) return;

  try {
    await api("/auth/me", { method: "DELETE" });
  } catch (error) {
    if (error.status !== 401) {
      toast(error.detail ?? "탈퇴를 완료하지 못했습니다. 다시 시도해 주세요.", "error");
      return;
    }
  }
  try {
    globalThis.sessionStorage?.clear();
  } catch {
    // 저장소를 쓸 수 없어도 탈퇴는 끝난 상태다
  }
  setUser(null);
  renderUserbar();
  renderTabbar();
  toast("회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.");
  router.navigate("/login");
}

/** 401 수신 시: 사용자 상태를 지우고, 돌아올 경로를 next 로 남긴 채 로그인으로 보낸다. */
function onSessionExpired() {
  if (!getUser()) return;
  setUser(null);
  renderUserbar();
  toast("세션이 만료되었습니다. 다시 로그인해 주세요.", "info");
  const { path, query } = parseHash(location.hash);
  const qs = new URLSearchParams(query).toString();
  router.replace("/login", { next: safeNext(qs ? `${path}?${qs}` : path, "/wordbooks") });
}

const routes = [
  { pattern: "/", access: "any", view: (_root, { replace }) => replace(getUser() ? "/wordbooks" : "/login") },
  { pattern: "/login", access: "guest", view: loginView },
  { pattern: "/signup", access: "guest", view: signupView },
  { pattern: "/wordbooks", access: "user", view: wordbooksView },
  { pattern: "/wordbooks/:id", access: "user", view: wordsView },
  { pattern: "/study/flashcards", access: "user", view: flashcardsView },
  { pattern: "/study/quiz", access: "user", view: quizView },
  { pattern: "/bookmarks", access: "user", view: bookmarksView },
  { pattern: "/history", access: "user", view: historyView },
];

const router = createRouter({
  routes,
  root,
  getUser,
  onNotFound: () => {
    clear(root);
    root.append(
      notice({
        iconName: "search-x",
        title: "페이지를 찾을 수 없습니다.",
        action: button({ variant: "secondary", onClick: () => router.navigate("/wordbooks") }, "단어장으로"),
      }),
    );
  },
});

/** Lucide 아이콘 자리표시자가 새로 생기면 SVG 로 바꾼다 (동적 화면·모달 포함). */
function watchIcons() {
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      for (const node of record.addedNodes) {
        if (!(node instanceof Element)) continue;
        if (node.matches("i[data-lucide]") || node.querySelector("i[data-lucide]")) {
          refreshIcons();
          return;
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

async function boot() {
  setUnauthorizedHandler(onSessionExpired);
  watchIcons();
  try {
    setUser(await api("/auth/me", { skipAuthRedirect: true }));
  } catch (error) {
    setUser(null);
    if (error.status === 0) {
      clear(root);
      root.append(
        notice({
          iconName: "wifi-off",
          title: "서버에 연결하지 못했습니다.",
          text: error.detail,
          action: button({ variant: "secondary", onClick: () => location.reload() }, "다시 시도"),
        }),
      );
      return;
    }
  }
  renderUserbar();
  router.start();
  renderTabbar();
  window.addEventListener("hashchange", () => { renderUserbar(); renderTabbar(); });
}

boot();
