/*
 * 2026-11-02 - voda-voca - 북마크 모아보기: 최신순 목록, 별 해제 시 즉시 제거(낙관적), 북마크 플래시카드·퀴즈 진입 (REQ-017, REQ-018, REQ-019)
 * 파일 위치: src/frontend/js/views/bookmarks.js
 */

import { api, ApiError } from "../core/api.js";
import { createBookmarkQueue } from "../core/bookmark.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { formatKst } from "../core/format.js";
import { toast } from "../core/toast.js";
import { canStartQuiz, QUIZ_MIN_WORDS } from "../lib/study-source.js";

export const BOOKMARK_PAGE_SIZE = 20;

/**
 * 북마크 화면 상태 분기 (순수 함수).
 * @param {{status: "loading"|"ok"|"error", items: unknown[]}} s
 * @returns {"loading"|"error"|"empty"|"success"}
 */
export function bookmarkListState(s) {
  if (s.status === "loading") return "loading";
  if (s.status === "error") return "error";
  return s.items.length === 0 ? "empty" : "success";
}

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function bookmarksView(root, { navigate }) {
  const controller = new AbortController();
  const state = { status: "loading", items: [], total: 0, page: 0, error: "", busy: false };
  const header = h("div", { class: "space-y-3" });
  const listEl = h("div", { class: "space-y-3" });
  const moreBtn = button({ variant: "secondary", full: true, onClick: loadMore }, "더 보기");
  moreBtn.hidden = true;
  root.append(header, listEl, h("div", { class: "mt-4" }, moreBtn));

  const queue = createBookmarkQueue({
    send: (wordId, on) => api(`/bookmarks/${wordId}`, { method: on ? "PUT" : "DELETE" }),
    onChange: (wordId, on, pending) => {
      if (!on) removeRow(wordId); // 해제하면 목록에서 즉시 뺀다 (낙관적 갱신)
      const btn = listEl.querySelector(`button.star-toggle[data-word-id="${wordId}"]`);
      btn?.setAttribute("aria-busy", String(pending));
    },
    onError: (wordId, error, attempted) => {
      toast(attempted ? "북마크를 바꾸지 못했습니다." : "북마크를 저장하지 못했습니다.", "error");
      load(true); // 되돌릴 행이 없으므로 목록을 다시 받는다
    },
  });

  async function load(reset) {
    if (reset) {
      state.items = [];
      state.page = 0;
    }
    state.status = "loading";
    render();
    try {
      const nextPage = state.page + 1;
      const data = await api("/bookmarks", { query: { page: nextPage, size: BOOKMARK_PAGE_SIZE }, signal: controller.signal });
      state.items = state.items.concat(data.items);
      state.total = data.total;
      state.page = nextPage;
      state.status = "ok";
      data.items.forEach((item) => queue.init(item.word_id, true));
    } catch (error) {
      if (error.name === "AbortError") return;
      state.status = "error";
      state.error = error instanceof ApiError ? error.detail : "북마크를 불러오지 못했습니다.";
    }
    render();
  }

  async function loadMore() {
    if (state.busy || state.status !== "ok") return;
    state.busy = true;
    moreBtn.disabled = true;
    try {
      const nextPage = state.page + 1;
      const data = await api("/bookmarks", { query: { page: nextPage, size: BOOKMARK_PAGE_SIZE }, signal: controller.signal });
      state.items = state.items.concat(data.items);
      state.total = data.total;
      state.page = nextPage;
      data.items.forEach((item) => queue.init(item.word_id, true));
      render();
    } catch (error) {
      if (error.name !== "AbortError") toast(error.detail ?? "더 불러오지 못했습니다.", "error");
    } finally {
      state.busy = false;
      moreBtn.disabled = false;
    }
  }

  /** @param {number} wordId */
  function removeRow(wordId) {
    const row = listEl.querySelector(`[data-word-id="${wordId}"]`);
    if (!row) return;
    row.remove();
    state.items = state.items.filter((item) => item.word_id !== wordId);
    state.total = Math.max(0, state.total - 1);
    if (state.items.length === 0 && state.status === "ok") render();
    else updateHeader();
  }

  function updateHeader() {
    const canQuiz = canStartQuiz(state.total);
    header.querySelector("[data-count]")?.replaceChildren(document.createTextNode(`총 ${state.total}개`));
    const quizBtn = header.querySelector("[data-quiz]");
    if (quizBtn) quizBtn.disabled = !canQuiz;
    const hint = header.querySelector("[data-hint]");
    if (hint) hint.textContent = canQuiz ? "" : `북마크가 ${QUIZ_MIN_WORDS}개 이상이면 퀴즈를 할 수 있습니다.`;
  }

  function render() {
    clear(header);
    const canQuiz = canStartQuiz(state.total);
    header.append(
      h(
        "div",
        { class: "flex items-baseline justify-between gap-2" },
        h("h1", { class: "text-xl font-bold" }, "북마크"),
        h("span", { class: "text-sm text-zinc-600", "data-count": "" }, `총 ${state.total}개`),
      ),
      h(
        "div",
        { class: "grid grid-cols-2 gap-2" },
        button({ variant: "secondary", disabled: state.total === 0, onClick: () => navigate("/study/flashcards", { bookmarked: "1" }) }, icon("layers"), "플래시카드"),
        button({ disabled: !canQuiz || state.total === 0, onClick: () => navigate("/study/quiz", { bookmarks: "1" }), "data-quiz": "" }, icon("list-checks"), "퀴즈"),
      ),
      h("p", { class: "text-xs text-zinc-500", "data-hint": "" }, canQuiz || state.status !== "ok" ? "" : `북마크가 ${QUIZ_MIN_WORDS}개 이상이면 퀴즈를 할 수 있습니다.`),
    );

    clear(listEl);
    const view = bookmarkListState(state);
    moreBtn.hidden = view !== "success" || state.items.length >= state.total;
    if (view === "loading") {
      listEl.append(skeleton(3));
    } else if (view === "error") {
      listEl.append(notice({ iconName: "cloud-off", title: "북마크를 불러오지 못했습니다.", text: state.error, action: button({ variant: "secondary", onClick: () => load(true) }, "다시 시도") }));
    } else if (view === "empty") {
      listEl.append(
        notice({
          iconName: "star",
          title: "북마크한 단어가 없습니다.",
          text: "단어장에서 별을 누르면 여기에 모입니다.",
          action: button({ variant: "secondary", onClick: () => navigate("/wordbooks") }, "단어장으로"),
        }),
      );
    } else {
      for (const item of state.items) listEl.append(row(item));
    }
    refreshIcons();
  }

  /** @param {{word_id: number, wordbook_id: number, wordbook_name: string, term: string, meaning: string, example: string|null, bookmarked_at: string}} item */
  function row(item) {
    queue.init(item.word_id, true);
    return h(
      "article",
      { class: "flex items-stretch surface", dataset: { wordId: String(item.word_id) } },
      h(
        "button",
        {
          type: "button",
          class: "flex min-h-[44px] flex-1 flex-col items-start gap-1 rounded-l-xl p-4 text-left hover:bg-zinc-50",
          onclick: () => navigate(`/wordbooks/${item.wordbook_id}`),
        },
        h("span", { class: "break-words text-lg font-semibold text-zinc-900" }, item.term),
        h("span", { class: "break-words text-sm text-zinc-700" }, item.meaning),
        h("span", { class: "rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600" }, item.wordbook_name),
        h("span", { class: "text-xs text-zinc-500" }, `북마크 ${formatKst(item.bookmarked_at)}`),
      ),
      h(
        "button",
        {
          type: "button",
          class: "star-toggle flex min-h-[44px] min-w-[44px] items-center justify-center self-center rounded-xl pr-1 hover:bg-amber-50",
          "aria-pressed": "true",
          "aria-label": `${item.term} 북마크 해제`,
          dataset: { wordId: String(item.word_id) },
          onclick: () => queue.toggle(item.word_id),
        },
        icon("star", "h-6 w-6"),
      ),
    );
  }

  load(true);
  return () => {
    controller.abort();
    queue.clear();
  };
}
