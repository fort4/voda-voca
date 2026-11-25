/*
 * 2026-11-05 - voda-voca - 단어 미리보기 바텀시트: 단어장의 단어를 읽기 전용으로 페이지씩 보여 주고 표제어·뜻으로 검색한다 (Esc·바깥 탭·✕ 로 닫기)
 * 파일 위치: src/frontend/js/views/components/word-sheet.js
 */

import { api } from "../../core/api.js";
import { button, h, icon, refreshIcons } from "../../core/dom.js";
import { INPUT_CLASS } from "../../core/form.js";
import { stopSpeaking } from "../../core/tts.js";
import { SEARCH_DEBOUNCE_MS, SEARCH_MAX_LENGTH, createWordPager, pagerFooter } from "../../core/word-search-model.js";
import { phoneticLine } from "./phonetic-line.js";
import { posTag } from "./pos-tag.js";
import { speakButton } from "./speak-button.js";

const PAGE_SIZE = 30;

/**
 * @param {{id: number, title: string}} vocabulary
 * @returns {void}
 */
export function openWordSheet(vocabulary) {
  const previousFocus = document.activeElement;
  const list = h("div", { class: "space-y-2" });
  const footer = h("div", { class: "pt-2", "aria-live": "polite" });
  let searchTimer;

  const pager = createWordPager({
    fetchPage: ({ page, query }) => api(`/vocabularies/${vocabulary.id}/words`, { query: { page, size: PAGE_SIZE, q: query || undefined } }),
    onChange: (event) => {
      if (event.type === "reset") {
        stopSpeaking(); // 재생 중인 단어의 버튼이 목록에서 사라진다
        list.replaceChildren();
      }
      if (event.type === "page") list.append(...event.added.map(wordRow));
      paintFooter();
      refreshIcons();
    },
  });

  function paintFooter() {
    const { kind, text } = pagerFooter(pager.state);
    if (kind === "more") {
      footer.replaceChildren(button({ variant: "secondary", full: true, onClick: pager.loadMore }, text));
    } else if (kind === "error") {
      footer.replaceChildren(h("p", { class: "text-sm text-red-600" }, text), button({ variant: "secondary", onClick: pager.loadMore }, "다시 시도"));
    } else {
      footer.replaceChildren(h("p", { class: "text-center text-sm text-zinc-500", "aria-busy": kind === "loading" ? "true" : undefined }, text));
    }
  }

  const searchInput = /** @type {HTMLInputElement} */ (
    h("input", {
      type: "search",
      class: INPUT_CLASS,
      placeholder: "표제어 또는 뜻 검색",
      "aria-label": "표제어 또는 뜻 검색",
      autocomplete: "off",
      autocapitalize: "none",
      enterkeyhint: "search",
      maxlength: SEARCH_MAX_LENGTH,
      oninput: () => {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(() => pager.search(searchInput.value), SEARCH_DEBOUNCE_MS);
      },
      onkeydown: (event) => {
        if (event.key !== "Enter" || event.isComposing) return; // 한글 조합을 끝내는 Enter 는 지나친다
        clearTimeout(searchTimer);
        pager.search(searchInput.value);
      },
    })
  );

  const close = () => {
    clearTimeout(searchTimer);
    stopSpeaking(); // 시트를 닫으면 재생 중인 발음도 멈춘다
    document.removeEventListener("keydown", onKey);
    overlay.remove();
    previousFocus?.focus?.();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };

  const panel = h(
    "div",
    { class: "surface w-full max-w-lg overflow-y-auto rounded-b-none p-4", role: "dialog", "aria-modal": "true", "aria-label": `${vocabulary.title} 미리보기`, style: "max-height: 80dvh; padding-bottom: max(1rem, env(safe-area-inset-bottom))" },
    h("div", { class: "mb-3 flex items-center justify-between gap-2" }, h("h2", { class: "min-w-0 truncate text-lg font-bold text-zinc-900" }, vocabulary.title), button({ variant: "ghost", "aria-label": "닫기", onClick: close }, icon("x", "h-5 w-5"))),
    h("div", { class: "mb-3" }, searchInput),
    list,
    footer,
  );
  const overlay = h("div", { class: "fixed inset-0 z-50 flex items-end justify-center", style: "background: rgba(0, 0, 0, 0.4)", onclick: (event) => event.target === overlay && close() }, panel);
  document.body.append(overlay);
  document.addEventListener("keydown", onKey);
  refreshIcons();
  pager.loadMore();
  panel.querySelector("button")?.focus(); // 닫기 버튼. 검색창에 바로 초점을 주면 모바일 키보드가 목록을 가린다
}

/** @param {{term: string, phonetic?: string|null, pos?: string|null, meaning: string, example: string|null}} word */
function wordRow(word) {
  return h(
    "div",
    { class: "flex items-start gap-2 rounded-xl bg-zinc-50 px-3 py-2" },
    h(
      "div",
      { class: "min-w-0 flex-1" },
      h("p", { class: "flex flex-wrap items-baseline gap-x-2" }, h("span", { class: "text-base font-semibold text-zinc-900 break-words" }, word.term), posTag(word.pos), phoneticLine(word.phonetic)),
      h("p", { class: "text-sm text-zinc-700" }, word.meaning),
      word.example ? h("p", { class: "mt-1 text-xs text-zinc-500" }, word.example) : null,
    ),
    h(
      "div",
      { class: "flex shrink-0 items-center" },
      // 미리보기는 단어를 훑어보는 용도라 표제어 듣기만 둔다 (예문 듣기는 학습 세션에서)
      speakButton({ text: word.term, kind: "word", key: `word:${word.term}` }),
    ),
  );
}
