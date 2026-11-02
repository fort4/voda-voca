/*
 * 2026-11-02 - voda-voca - 단어 목록 화면: 실시간 표제어 검색, 더 보기, 북마크 낙관적 토글, 단건 등록·수정·삭제, 일괄 등록 진입 (REQ-009~011, REQ-017, REQ-018)
 * 파일 위치: src/frontend/js/views/words.js
 */

import { api, ApiError } from "../core/api.js";
import { createBookmarkQueue } from "../core/bookmark.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { INPUT_CLASS } from "../core/form.js";
import { createSearch } from "../core/search.js";
import { confirmDialog, toast } from "../core/toast.js";
import { speak } from "../core/tts.js";
import { openBulkImport } from "./bulk-import.js";
import { openWordForm } from "./word-form.js";

export const WORD_PAGE_SIZE = 20;

/**
 * 목록 표시 상태. 화면 없이 테스트할 수 있도록 분리했다.
 * @param {{status: "loading"|"refreshing"|"ok"|"error", items: unknown[], total: number, q: string}} s
 * @returns {"loading"|"error"|"empty"|"search-empty"|"success"}
 */
export function wordListState(s) {
  if (s.status === "error") return "error";
  if (s.status === "loading" && s.items.length === 0) return "loading";
  if (s.items.length === 0) return s.q ? "search-empty" : "empty";
  return "success";
}

/**
 * @param {HTMLElement} root
 * @param {{params: {id: string}, navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function wordsView(root, { params, navigate }) {
  const wordbookId = Number(params.id);
  const controller = new AbortController();
  const state = { status: "loading", items: [], total: 0, q: "", page: 0, error: "", moreBusy: false, name: "" };
  let token = 0; // 검색어가 바뀔 때마다 증가. 오래된 "더 보기" 응답을 버린다.

  if (!Number.isInteger(wordbookId) || wordbookId <= 0) {
    root.append(notFound());
    return () => {};
  }

  const title = h("h1", { class: "min-w-0 flex-1 truncate text-xl font-bold" }, "단어장");
  const input = /** @type {HTMLInputElement} */ (
    h("input", {
      type: "search",
      enterkeyhint: "search",
      autocomplete: "off",
      placeholder: "표제어 앞부분으로 검색",
      "aria-label": "표제어 검색",
      class: `${INPUT_CLASS} pr-12`,
      oninput: (e) => search.setQuery(/** @type {HTMLInputElement} */ (e.target).value),
    })
  );
  const clearBtn = button({ variant: "ghost", onClick: () => { input.value = ""; search.flush(""); input.focus(); } }, h("span", { class: "sr-only" }, "검색어 지우기"), icon("x", "h-5 w-5"));
  clearBtn.hidden = true;
  const listEl = h("div", { class: "space-y-3 transition-opacity", "aria-live": "polite" });
  const moreBtn = button({ variant: "secondary", full: true, onClick: loadMore }, "더 보기");
  moreBtn.hidden = true;

  const bookmarks = createBookmarkQueue({
    send: (wordId, on) => api(`/bookmarks/${wordId}`, { method: on ? "PUT" : "DELETE" }),
    onChange: (wordId, on, pending) => paintStar(wordId, on, pending),
    onError: (wordId, error, attempted) => {
      toast(attempted ? "북마크를 저장하지 못했습니다." : "북마크를 바꾸지 못했습니다.", "error");
      if (error instanceof ApiError && error.status === 404) refresh();
    },
  });

  const search = createSearch({
    run: (q, signal) =>
      api(`/wordbooks/${wordbookId}/words`, { query: { q: q || undefined, page: 1, size: WORD_PAGE_SIZE }, signal }),
    onLoading: (q) => {
      token += 1;
      state.q = q;
      state.status = state.items.length ? "refreshing" : "loading";
      clearBtn.hidden = !q;
      render();
    },
    onResult: (data) => {
      state.items = data.items;
      state.total = data.total;
      state.page = 1;
      state.status = "ok";
      state.error = "";
      data.items.forEach((word) => bookmarks.init(word.id, word.bookmarked));
      render();
    },
    onError: (error) => {
      state.status = "error";
      state.error = error instanceof ApiError ? error.detail : "단어를 불러오지 못했습니다.";
      render();
    },
  });

  root.append(
    h(
      "div",
      { class: "mb-4 flex items-center gap-2" },
      button({ variant: "ghost", onClick: () => navigate("/wordbooks") }, icon("arrow-left"), h("span", { class: "sr-only" }, "단어장 목록으로")),
      title,
    ),
    h(
      "div",
      { class: "mb-3 grid grid-cols-2 gap-2" },
      button({ variant: "secondary", onClick: () => navigate("/study/flashcards", { wordbook_id: String(wordbookId) }) }, icon("layers"), "플래시카드"),
      button({ variant: "secondary", onClick: () => navigate("/study/quiz", { wordbook_id: String(wordbookId) }) }, icon("list-checks"), "퀴즈"),
      button({ variant: "secondary", onClick: () => openBulkImport({ wordbookId, onDone: refresh }) }, icon("upload"), "일괄 등록"),
      button({ onClick: () => openWordForm({ wordbookId, onChanged: refresh }) }, icon("plus"), "단어 추가"),
    ),
    h("div", { class: "relative mb-3" }, input, h("div", { class: "absolute right-1 top-1" }, clearBtn)),
    listEl,
    h("div", { class: "mt-4" }, moreBtn),
    h(
      "div",
      { class: "mt-8 border-t border-zinc-200 pt-4 flex justify-end" },
      button({ variant: "danger-soft", onClick: removeWordbook }, icon("trash-2", "h-4 w-4"), "단어장 삭제"),
    ),
  );

  /** 단어장 삭제: 되돌릴 수 없으므로 확인 창에서 CASCADE 범위를 분명히 알린다 (REQ-007). 성공하면 목록으로 간다. */
  async function removeWordbook() {
    const name = title.textContent || "이 단어장";
    const ok = await confirmDialog({
      title: "단어장을 삭제할까요?",
      text: `'${name}' 안의 모든 단어, 북마크, 학습 기록이 함께 영구 삭제됩니다. 되돌릴 수 없습니다.`,
      confirmText: "단어장 삭제",
      danger: true,
    });
    if (!ok) return;
    try {
      await api(`/wordbooks/${wordbookId}`, { method: "DELETE" });
      toast("단어장을 삭제했습니다.");
      navigate("/wordbooks");
    } catch (error) {
      toast(error.detail ?? "단어장을 삭제하지 못했습니다.", "error");
      if (error.status === 404) navigate("/wordbooks");
    }
  }

  /** 화면 전체를 현재 상태로 다시 그린다. */
  function render() {
    clear(listEl);
    listEl.classList.toggle("opacity-50", state.status === "refreshing");
    const view = wordListState(state);
    moreBtn.hidden = view !== "success" || state.items.length >= state.total;
    if (view === "loading") {
      listEl.append(skeleton(4));
    } else if (view === "error") {
      listEl.append(
        notice({
          iconName: "cloud-off",
          title: "단어를 불러오지 못했습니다.",
          text: state.error,
          action: button({ variant: "secondary", onClick: refresh }, "다시 시도"),
        }),
      );
    } else if (view === "empty") {
      listEl.append(
        notice({
          iconName: "book-open",
          title: "아직 단어가 없습니다.",
          text: "단어를 추가하거나 파일로 한 번에 등록해 보세요.",
          action: button({ onClick: () => openWordForm({ wordbookId, onChanged: refresh }) }, "단어 추가"),
        }),
      );
    } else if (view === "search-empty") {
      listEl.append(
        notice({
          iconName: "search-x",
          title: `'${state.q}'(으)로 시작하는 단어가 없습니다.`,
          action: button({ variant: "secondary", onClick: () => { input.value = ""; search.flush(""); input.focus(); } }, "검색 지우기"),
        }),
      );
    } else {
      for (const word of state.items) listEl.append(row(word));
    }
    refreshIcons();
  }

  /** @param {{id: number, term: string, meaning: string, example: string|null, bookmarked: boolean}} word */
  function row(word) {
    const current = bookmarks.getState(word.id)?.bookmarked ?? word.bookmarked;
    return h(
      "article",
      { class: "flex items-stretch surface", dataset: { wordId: String(word.id) } },
      h(
        "button",
        {
          type: "button",
          class: "flex min-h-[44px] flex-1 flex-col items-start gap-1 rounded-l-xl p-4 text-left hover:bg-zinc-50",
          onclick: () => openWordForm({ wordbookId, word, onChanged: refresh }),
        },
        h("span", { class: "text-lg font-semibold text-zinc-900 break-words" }, word.term),
        h("span", { class: "text-sm text-zinc-700 break-words" }, word.meaning),
        word.example ? h("span", { class: "text-sm text-zinc-500 break-words line-clamp-2" }, word.example) : null,
      ),
      h(
        "button",
        {
          type: "button",
          class: "press focus-ring flex min-h-[44px] min-w-[44px] shrink-0 items-center justify-center self-center rounded-xl text-zinc-400 hover:bg-indigo-50 hover:text-indigo-600",
          "aria-label": `${word.term} 발음 듣기`,
          onclick: (e) => {
            e.stopPropagation();
            speak(word.term);
          },
        },
        icon("volume-2", "h-5 w-5"),
      ),
      h(
        "button",
        {
          type: "button",
          class: "star-toggle flex min-h-[44px] min-w-[44px] items-center justify-center self-center rounded-xl pr-1 text-zinc-400 hover:bg-amber-50",
          "aria-pressed": String(current),
          "aria-label": `${word.term} 북마크`,
          dataset: { wordId: String(word.id) },
          onclick: () => bookmarks.toggle(word.id),
        },
        icon("star", "h-6 w-6"),
      ),
    );
  }

  /** 북마크 상태를 화면에 반영한다. 전송 중에는 aria-busy 로 표시한다. */
  function paintStar(wordId, on, pending) {
    const btn = listEl.querySelector(`button.star-toggle[data-word-id="${wordId}"]`);
    if (!btn) return;
    btn.setAttribute("aria-pressed", String(on));
    btn.setAttribute("aria-busy", String(pending));
  }

  /** 검색어 기준으로 처음부터 다시 받는다 (단건·일괄 등록 뒤 등). */
  function refresh() {
    search.flush(input.value);
  }

  /** 더 보기: 같은 검색어의 다음 페이지를 붙인다. */
  async function loadMore() {
    if (state.moreBusy || state.status !== "ok") return;
    const mine = token;
    const nextPage = state.page + 1;
    state.moreBusy = true;
    moreBtn.disabled = true;
    try {
      const data = await api(`/wordbooks/${wordbookId}/words`, {
        query: { q: state.q || undefined, page: nextPage, size: WORD_PAGE_SIZE },
        signal: controller.signal,
      });
      if (mine !== token) return; // 검색어가 바뀌었으면 버린다
      state.items = state.items.concat(data.items);
      state.total = data.total;
      state.page = nextPage;
      data.items.forEach((word) => bookmarks.init(word.id, word.bookmarked));
      render();
    } catch (error) {
      if (error.name !== "AbortError") toast(error.detail ?? "더 불러오지 못했습니다.", "error");
    } finally {
      state.moreBusy = false;
      moreBtn.disabled = false;
    }
  }

  /** 단어장 이름을 먼저 확인한다. 없거나 타인 것이면 404 안내. */
  (async () => {
    try {
      const wordbook = await api(`/wordbooks/${wordbookId}`, { signal: controller.signal });
      title.textContent = wordbook.name;
      search.flush("");
    } catch (error) {
      if (error.name === "AbortError") return;
      clear(root);
      root.append(error.status === 404 ? notFound() : notice({ iconName: "cloud-off", title: "단어장을 불러오지 못했습니다.", text: error.detail }));
    }
  })();

  return () => {
    search.cancel();
    controller.abort();
    bookmarks.clear();
  };

  function notFound() {
    return notice({
      iconName: "search-x",
      title: "단어장을 찾을 수 없습니다.",
      action: button({ variant: "secondary", onClick: () => navigate("/wordbooks") }, "단어장 목록으로"),
    });
  }
}
