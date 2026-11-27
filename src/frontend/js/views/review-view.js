/*
 * 2026-11-05 - voda-voca - 복습함 화면: 북마크·오답 단어 목록(탭, 10개씩 쪽 넘기기)과 복습 전용 세션 시작
 * 파일 위치: src/frontend/js/views/review-view.js
 */

import { api } from "../core/api.js";
import { appendNodes, button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { loadMode, saveMode } from "../core/home-model.js";
import { REVIEW_PAGE_SIZE, createPagedList, pagerModel } from "../core/paged-list.js";
import { bookmarkRow, dueSource, initialReviewTab, reviewSources } from "../core/review-model.js";
import { toast } from "../core/toast.js";
import { cardHeading, iconBadge } from "./components/card-heading.js";
import { mountLoader } from "./components/loader.js";
import { renderModeToggle } from "./components/mode-toggle.js";
import { phoneticLine } from "./components/phonetic-line.js";
import { posTag } from "./components/pos-tag.js";
import { openSession } from "./components/study-nav.js";

const TABS = [
  { id: "bookmarks", label: "북마크", path: "/bookmarks", iconName: "bookmark", tone: "tone-activity" },
  { id: "wrong", label: "틀린 단어", path: "/study/wrong-words", iconName: "rotate-ccw", tone: "tone-wrong" },
];

/** 두 목록의 첫 페이지와 오늘 복습 개수를 함께 읽는다. 총 개수가 곧 시작 가능 여부의 기준이다. 통계 실패는 카드만 "불러오는 중"으로 둔다. */
async function loadFirstPages() {
  const [bookmarks, wrong] = await Promise.all(TABS.map((tab) => api(tab.path, { query: { page: 1, size: REVIEW_PAGE_SIZE } })));
  const stats = await api("/study/stats").catch(() => null);
  return { bookmarks, wrong, dueCount: stats ? stats.due_review_count : null };
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void, query?: Record<string, string>}} ctx
 * @returns {() => void}
 */
export function reviewView(root, ctx) {
  let panel = null;
  const dispose = mountLoader(root, loadFirstPages, (pages) => {
    panel = new ReviewPanel(pages, ctx);
    root.append(panel.element);
  });
  return () => {
    dispose();
    panel?.dispose();
  };
}

class ReviewPanel {
  constructor(pages, ctx) {
    this.ctx = ctx;
    this.active = initialReviewTab(ctx.query);
    this.mode = loadMode(globalThis.localStorage);
    // 탭마다 보던 쪽을 따로 기억한다
    this.lists = Object.fromEntries(
      TABS.map((tab) => [
        tab.id,
        createPagedList({
          first: pages[tab.id],
          fetchPage: (page) => api(tab.path, { query: { page, size: REVIEW_PAGE_SIZE } }),
          onChange: (change) => this.onListChange(tab.id, change),
          onError: (error) => toast(error?.detail ?? "목록을 불러오지 못했어요.", "error"),
        }),
      ]),
    );
    this.dueCount = pages.dueCount;
    this.body = h("div", { class: "space-y-4" });
    this.element = h("div", { class: "stack pb-4" }, h("h1", { class: "text-title tracking-tight text-zinc-900" }, "복습함"), this.body);
    this.paint();
  }

  setMode(next) {
    this.mode = next;
    saveMode(globalThis.localStorage, next);
  }

  paint() {
    clear(this.body);
    const sources = reviewSources({ bookmarkCount: this.lists.bookmarks.state.total, wrongCount: this.lists.wrong.state.total });
    const source = sources.find((s) => s.id === this.active);
    const { iconName, tone } = TABS.find((t) => t.id === this.active);
    this.listElement = h("div", { class: `scroll-mt-20 space-y-2 ${tone}` });
    this.pager = pagerModel(this.lists[this.active].state).show ? this.createPager() : null;
    this.paintList();
    // 한 쪽에 다 들어가면 쪽 넘기기 자리는 null 이다. 네이티브 append 는 null 을 "null" 글자로 그리므로 appendNodes 로 거른다.
    appendNodes(
      this.body,
      renderModeToggle({ value: this.mode, onChange: (next) => this.setMode(next) }),
      this.dueCard(),
      h("div", { class: "segmented grid-cols-2", role: "tablist" }, TABS.map((tab) => this.tab(tab, sources))),
      h("section", { class: `card ${tone} space-y-3` }, h("div", { class: "flex items-center gap-3" }, iconBadge(iconName), h("p", { class: "min-w-0 text-sm text-zinc-700" }, source.message)), button({ variant: "primary", full: true, disabled: !source.ready, onClick: () => openSession(this.ctx.navigate, this.mode, this.active) }, icon("play", "h-5 w-5"), "복습 시작")),
      this.listElement,
      this.pager?.element ?? null,
    );
    refreshIcons();
  }

  /** 오늘 복습(SRS) 카드: 복습 예정 시각이 도래한 단어로 바로 세션을 시작한다. */
  dueCard() {
    const due = dueSource(this.dueCount);
    return h("section", { class: "card tone-accent space-y-3" }, cardHeading({ iconName: "calendar-clock", title: "오늘 복습" }), h("p", { class: "text-sm text-zinc-700" }, due.message), button({ variant: "primary", full: true, disabled: !due.ready, onClick: () => openSession(this.ctx.navigate, this.mode, "due") }, icon("play", "h-5 w-5"), "오늘 복습 시작"));
  }

  tab(tab, sources) {
    const on = tab.id === this.active;
    const count = sources.find((s) => s.id === tab.id).count;
    return h("button", { type: "button", role: "tab", "aria-selected": String(on), class: "segment press focus-ring", onclick: () => { this.active = tab.id; this.paint(); } }, `${tab.label} ${count ?? ""}`.trim());
  }

  row(r) {
    return h("div", { class: "surface word-row px-4 py-3" }, h("div", { class: "flex items-baseline justify-between gap-2" }, h("p", { class: "flex min-w-0 flex-wrap items-baseline gap-x-2" }, h("span", { class: "text-base font-semibold text-zinc-900 break-words" }, r.term), posTag(r.pos), phoneticLine(r.phonetic)), h("p", { class: "shrink-0 text-xs text-zinc-500" }, r.source)), h("p", { class: "text-sm text-zinc-700" }, r.meaning));
  }

  /** 이전·다음 줄. 버튼은 다시 만들지 않고 상태만 바꿔 키보드 포커스를 지킨다. */
  createPager() {
    const list = this.lists[this.active];
    const prev = button({ variant: "secondary", onClick: () => list.goTo(list.state.page - 1) }, icon("chevron-left", "h-4 w-4"), "이전");
    const next = button({ variant: "secondary", onClick: () => list.goTo(list.state.page + 1) }, "다음", icon("chevron-right", "h-4 w-4"));
    const label = h("p", { class: "text-sm font-semibold text-zinc-700", "aria-live": "polite" });
    const element = h("nav", { class: "flex items-center justify-between gap-3", "aria-label": `${TABS.find((t) => t.id === this.active).label} 목록 쪽 넘기기` }, prev, label, next);
    return { element, prev, next, label };
  }

  /** 보고 있는 탭의 목록과 쪽 상태만 다시 그린다. */
  paintList() {
    const { items, busy } = this.lists[this.active].state;
    const empty = this.active === "bookmarks" ? "북마크한 단어가 없어요. 학습 중 ★ 를 눌러 모아 보세요." : "틀린 단어가 없어요. 잘하고 있어요!";
    this.listElement.setAttribute("aria-busy", String(busy));
    this.listElement.replaceChildren(...(items.length === 0 ? [h("p", { class: "card text-center text-sm text-zinc-600" }, empty)] : items.map((item) => this.row(bookmarkRow(item)))));
    if (!this.pager) return;
    const model = pagerModel(this.lists[this.active].state);
    // disabled 는 포커스를 잃게 하므로 aria-disabled 로 잠근다. 잠긴 동안의 누름은 목록 상태 관리가 무시한다.
    this.pager.prev.setAttribute("aria-disabled", String(model.prevDisabled));
    this.pager.next.setAttribute("aria-disabled", String(model.nextDisabled));
    this.pager.label.textContent = model.label;
  }

  /** 다른 탭의 늦은 응답은 그 탭의 상태에만 남긴다. 전체 개수가 달라지면 탭 숫자와 시작 카드까지 다시 그린다. */
  onListChange(tabId, { moved, totalChanged }) {
    if (totalChanged) this.paint();
    if (tabId !== this.active) return;
    if (!totalChanged) this.paintList();
    // 아래의 버튼으로 넘겼으면 새 쪽의 첫 줄이 화면 위로 벗어나 있을 수 있다 (상단 헤더 높이만큼 여유)
    if (moved && this.listElement.getBoundingClientRect().top < 80) this.listElement.scrollIntoView({ block: "start" });
  }

  dispose() {
    Object.values(this.lists).forEach((list) => list.dispose());
  }
}
