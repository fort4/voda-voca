/*
 * 2026-11-05 - voda-voca - 앱 진입점: 세션 확인(/auth/me), 라우트 등록, 상단바·하단 탭바, 세션 만료 처리 (REQ-001, REQ-002)
 * 파일 위치: src/frontend/js/app.js
 */

import { api, setUnauthorizedHandler } from "./core/api.js";
import { nicknameConfirmationMatches } from "./core/validate.js";
import { button, clear, h, notice, refreshIcons, icon } from "./core/dom.js";
import { createRouter, parseHash, safeNext } from "./core/router.js";
import { noticeMessage, setSpeechNotifier, stopSpeaking } from "./core/tts.js";
import { buildRoutes } from "./routes.js";
import { getUser, setUser } from "./core/state.js";
import { confirmDialog, toast } from "./core/toast.js";
import { loginView } from "./views/login.js";
import { createThemeManager } from "./core/theme.js";
import { isMuted, toggleMute } from "./core/sound.js";
import { signupView } from "./views/signup.js";
import { exploreView } from "./views/explore-view.js";
import { homeView } from "./views/home-view.js";
import { reviewView } from "./views/review-view.js";
import { statsView } from "./views/stats-view.js";
import { studySessionView } from "./views/study-session-view.js";
import { renderBottomNav } from "./views/components/bottom-nav.js";

const root = /** @type {HTMLElement} */ (document.getElementById("app"));
const userbar = /** @type {HTMLElement} */ (document.getElementById("userbar"));
const tabbar = /** @type {HTMLElement} */ (document.getElementById("tabbar"));

/** 하단 탭바: 로그인 상태이고 인증 화면·학습 세션이 아닐 때만 보인다 (규칙은 core/nav.js). */
function renderTabbar() {
  renderBottomNav(tabbar, { path: parseHash(location.hash).path, user: getUser() });
}

/** 상단바: 로그인 상태에 따라 계정 메뉴(닉네임 칩), 또는 로그인 링크를 보인다. */
function renderUserbar() {
  clear(userbar);
  const user = getUser();
  if (user) {
    const trigger = button(
      {
        variant: "ghost",
        onClick: () => toggleAccountMenu(trigger),
        "aria-label": `${user.nickname} 계정 메뉴`,
        "aria-haspopup": "menu",
        "aria-expanded": "false",
      },
      h("span", { class: "grid h-7 w-7 place-items-center rounded-full bg-indigo-600 text-xs font-bold text-white" }, initialOf(user.nickname)),
      h("span", { class: "hidden max-w-[9rem] truncate text-sm font-medium text-zinc-700 sm:inline" }, user.nickname),
      icon("chevron-down", "h-4 w-4 text-zinc-400"),
    );
    userbar.append(trigger);
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

/** 열려 있는 계정 드롭다운. 없으면 null. */
let accountMenu = null;

/** @param {HTMLElement} anchor 프로필 칩 */
function toggleAccountMenu(anchor) {
  if (accountMenu) closeAccountMenu();
  else openAccountMenu(anchor);
}

/**
 * 프로필 칩 바로 아래에 붙는 플로팅 드롭다운을 연다. 바깥 클릭이나 ESC 로 닫힌다.
 * 로그아웃은 확인 없이 즉시 처리하고, 회원 탈퇴는 기존 두 단계 확인 흐름을 쓴다.
 * @param {HTMLElement} anchor
 */
function openAccountMenu(anchor) {
  const user = getUser();
  if (!user) return;
  const backdrop = h("div", { class: "dropdown-backdrop", onclick: closeAccountMenu });
  const popover = h(
    "div",
    { class: "dropdown-popover", role: "menu", "aria-label": "계정 메뉴" },
    h(
      "div",
      { class: "flex items-center gap-3 px-3 py-3" },
      h("span", { class: "grid h-10 w-10 shrink-0 place-items-center rounded-full bg-indigo-600 text-sm font-bold text-white" }, initialOf(user.nickname)),
      h(
        "div",
        { class: "min-w-0" },
        h("p", { class: "truncate text-sm font-semibold text-zinc-900" }, user.nickname),
        h("span", { class: "chip-sm" }, "학습자"),
      ),
    ),
    h("div", { class: "dropdown-divider" }),
    menuItem("log-out", "로그아웃", logoutFromMenu),
    h("div", { class: "dropdown-divider" }),
    h(
      "div",
      { class: "dropdown-danger-zone" },
      menuItem("user-x", "회원 탈퇴", withdrawFromMenu, "danger"),
    ),
  );

  const rect = anchor.getBoundingClientRect();
  popover.style.top = `${rect.bottom + 8}px`;
  popover.style.right = `${Math.max(8, window.innerWidth - rect.right)}px`;
  document.body.append(backdrop, popover);
  anchor.setAttribute("aria-expanded", "true");
  const onKey = (event) => {
    if (event.key === "Escape") closeAccountMenu();
  };
  document.addEventListener("keydown", onKey);
  accountMenu = { backdrop, popover, anchor, onKey };
  refreshIcons();
  popover.querySelector("button")?.focus();
}

function closeAccountMenu() {
  if (!accountMenu) return;
  const { backdrop, popover, anchor, onKey } = accountMenu;
  document.removeEventListener("keydown", onKey);
  backdrop.remove();
  popover.remove();
  anchor.setAttribute("aria-expanded", "false");
  accountMenu = null;
}

/**
 * @param {string} iconName
 * @param {string} label
 * @param {() => void} onSelect
 * @param {"default"|"danger"} [tone]
 */
function menuItem(iconName, label, onSelect, tone = "default") {
  return h(
    "button",
    {
      type: "button",
      role: "menuitem",
      class: tone === "danger" ? "dropdown-item dropdown-item--danger" : "dropdown-item",
      onclick: onSelect,
    },
    icon(iconName, "h-5 w-5"),
    h("span", {}, label),
  );
}

function logoutFromMenu() {
  closeAccountMenu();
  return logout();
}

function withdrawFromMenu() {
  closeAccountMenu();
  return withdraw();
}

async function logout() {
  try {
    await api("/auth/logout", { method: "POST", skipAuthRedirect: true });
  } catch {
    // 세션이 이미 없어도 로컬 상태는 지운다
  }
  setUser(null);
  renderUserbar();
  renderTabbar();
  toast("로그아웃되었습니다.", "info");
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
    text: "계정과 북마크, 학습 기록이 영구 삭제됩니다. 되돌릴 수 없습니다.",
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
  router.replace("/login", { next: safeNext(qs ? `${path}?${qs}` : path) });
}

const routes = buildRoutes({
  login: loginView,
  signup: signupView,
  home: homeView,
  explore: exploreView,
  session: studySessionView,
  review: reviewView,
  stats: statsView,
});

const router = createRouter({
  routes,
  root,
  getUser,
  afterRender: refreshIcons,
  onNotFound: () => {
    clear(root);
    root.append(
      notice({
        iconName: "search-x",
        title: "페이지를 찾을 수 없습니다.",
        action: button({ variant: "secondary", onClick: () => router.navigate("/") }, "홈으로"),
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

/**
 * 정답 소리 버튼: 저장된 음소거 상태에 맞춰 아이콘과 라벨을 그리고, 누르면 켜고 끈다.
 * 오답에는 소리가 없으므로 이 버튼은 정답 효과음만 제어한다.
 */
function initSound() {
  const btn = document.getElementById("sound-toggle");
  if (!btn) return;
  const paint = () => {
    const muted = isMuted();
    btn.setAttribute("aria-pressed", String(!muted));
    btn.setAttribute("aria-label", muted ? "정답 소리 켜기" : "정답 소리 끄기");
    btn.replaceChildren(h("i", { "data-lucide": muted ? "volume-x" : "volume-2", class: "h-5 w-5", "aria-hidden": "true" }));
    refreshIcons();
  };
  btn.addEventListener("click", () => {
    toggleMute();
    paint();
  });
  paint();
}

/**
 * 테마 초기화: 관리자 생성(저장값 > 시스템 설정), 전환 버튼 아이콘과 클릭 연결.
 * 첫 페이지 깜빡임은 index.html 의 인라인 스크립트가 막고, 여기서는 버튼 상태를 맞춘다.
 */
function initTheme() {
  const manager = createThemeManager();
  const toggleBtn = document.getElementById("theme-toggle");
  const paint = () => {
    const dark = manager.current() === "dark";
    if (toggleBtn) {
      toggleBtn.setAttribute("aria-pressed", String(dark));
      toggleBtn.setAttribute("aria-label", dark ? "라이트 모드로 전환" : "다크 모드로 전환");
      toggleBtn.replaceChildren(h("i", { "data-lucide": dark ? "sun" : "moon", class: "h-5 w-5", "aria-hidden": "true" }));
      refreshIcons();
    }
  };
  toggleBtn?.addEventListener("click", () => {
    manager.toggle();
    paint();
  });
  paint();
  return manager;
}

async function boot() {
  setUnauthorizedHandler(onSessionExpired);
  initTheme();
  initSound();
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
  window.addEventListener("hashchange", () => { stopSpeaking(); renderUserbar(); renderTabbar(); });
  // 발음 재생 불가 안내(자동재생 차단, 영어 음성 없음, 미지원)는 세션당 한 번 토스트로 알린다
  setSpeechNotifier((reason) => toast(noticeMessage(reason), "warning"));
  // 탭을 숨기거나 떠나면 발음을 멈춘다 (모바일에서 백그라운드 재생 방지)
  document.addEventListener("visibilitychange", () => { if (document.hidden) stopSpeaking(); });
  window.addEventListener("pagehide", stopSpeaking);
}

boot();
