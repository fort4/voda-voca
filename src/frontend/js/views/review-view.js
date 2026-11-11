/*
 * 2026-11-05 - voda-voca - 복습함 화면: 북마크·오답 단어 목록(탭, 더 보기)과 복습 전용 세션 시작
 * 파일 위치: src/frontend/js/views/review-view.js
 */

import { api } from "../core/api.js";
import { appendNodes, button, clear, h, icon, refreshIcons } from "../core/dom.js";
import { loadMode } from "../core/home-model.js";
import { bookmarkRow, reviewSources } from "../core/review-model.js";
import { mountLoader } from "./components/loader.js";
import { phoneticLine } from "./components/phonetic-line.js";
import { posTag } from "./components/pos-tag.js";
import { openSession } from "./components/study-nav.js";

const PAGE_SIZE = 20;
const TABS = [
  { id: "bookmarks", label: "북마크", path: "/bookmarks" },
  { id: "wrong", label: "틀린 단어", path: "/study/wrong-words" },
];

/** 두 목록의 첫 페이지를 함께 읽는다. 총 개수가 곧 시작 가능 여부의 기준이다. */
async function loadFirstPages() {
  const [bookmarks, wrong] = await Promise.all(TABS.map((tab) => api(tab.path, { query: { page: 1, size: PAGE_SIZE } })));
  return { bookmarks, wrong };
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: Record<string, string>) => void}} ctx
 * @returns {() => void}
 */
export function reviewView(root, ctx) {
  return mountLoader(root, loadFirstPages, (pages) => root.append(new ReviewPanel(pages, ctx).element));
}

class ReviewPanel {
  constructor(pages, ctx) {
    this.ctx = ctx;
    this.active = "bookmarks";
    this.data = { bookmarks: { items: pages.bookmarks.items, total: pages.bookmarks.total, page: 1 }, wrong: { items: pages.wrong.items, total: pages.wrong.total, page: 1 } };
    this.body = h("div", { class: "space-y-4" });
    this.element = h("div", { class: "stack pb-4" }, h("h1", { class: "text-title tracking-tight text-zinc-900" }, "복습함"), this.body);
    this.paint();
  }

  paint() {
    clear(this.body);
    const sources = reviewSources({ bookmarkCount: this.data.bookmarks.total, wrongCount: this.data.wrong.total });
    const source = sources.find((s) => s.id === this.active);
    const current = this.data[this.active];
    // 목록이 끝났으면 "더 보기" 자리는 null 이다. 네이티브 append 는 null 을 "null" 글자로 그리므로 appendNodes 로 거른다.
    appendNodes(
      this.body,
      h("div", { class: "grid grid-cols-2 gap-1 rounded-xl bg-zinc-100 p-1", role: "tablist" }, TABS.map((tab) => this.tab(tab, sources))),
      h("section", { class: "card space-y-3" }, h("p", { class: "text-sm text-zinc-700" }, source.message), button({ variant: "primary", full: true, disabled: !source.ready, onClick: () => openSession(this.ctx.navigate, loadMode(globalThis.localStorage), this.active) }, icon("play", "h-5 w-5"), "복습 시작")),
      current.items.length === 0 ? h("p", { class: "surface p-6 text-center text-sm text-zinc-600" }, this.active === "bookmarks" ? "북마크한 단어가 없어요. 학습 중 ★ 를 눌러 모아 보세요." : "틀린 단어가 없어요. 잘하고 있어요!") : h("div", { class: "space-y-2" }, current.items.map((item) => this.row(bookmarkRow(item)))),
      current.items.length < current.total ? button({ variant: "secondary", full: true, onClick: () => this.more() }, `더 보기 (${current.items.length}/${current.total})`) : null,
    );
    refreshIcons();
  }

  tab(tab, sources) {
    const on = tab.id === this.active;
    const count = sources.find((s) => s.id === tab.id).count;
    return h("button", { type: "button", role: "tab", "aria-selected": String(on), class: `press focus-ring min-h-[44px] rounded-lg px-3 text-body font-semibold ${on ? "bg-white text-indigo-600 shadow-sm" : "text-zinc-600"}`, onclick: () => { this.active = tab.id; this.paint(); } }, `${tab.label} ${count ?? ""}`.trim());
  }

  row(r) {
    return h("div", { class: "surface px-4 py-3" }, h("div", { class: "flex items-baseline justify-between gap-2" }, h("p", { class: "flex min-w-0 flex-wrap items-baseline gap-x-2" }, h("span", { class: "text-base font-semibold text-zinc-900 break-words" }, r.term), posTag(r.pos), phoneticLine(r.phonetic)), h("p", { class: "shrink-0 text-xs text-zinc-500" }, r.source)), h("p", { class: "text-sm text-zinc-700" }, r.meaning));
  }

  async more() {
    const tab = TABS.find((t) => t.id === this.active);
    const current = this.data[tab.id];
    try {
      const next = await api(tab.path, { query: { page: current.page + 1, size: PAGE_SIZE } });
      this.data[tab.id] = { items: [...current.items, ...next.items], total: next.total, page: current.page + 1 };
    } catch {
      // 목록은 그대로 두고 버튼으로 다시 누를 수 있게 한다
    }
    this.paint();
  }
}
