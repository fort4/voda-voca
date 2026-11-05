/*
 * 2026-11-05 - voda-voca - 단어 미리보기 바텀시트: 단어장의 단어를 읽기 전용으로 페이지씩 보여 준다 (Esc·바깥 탭·✕ 로 닫기)
 * 파일 위치: src/frontend/js/views/components/word-sheet.js
 */

import { api } from "../../core/api.js";
import { button, h, icon, refreshIcons } from "../../core/dom.js";
import { stopSpeaking } from "../../core/tts.js";
import { speakButton } from "./speak-button.js";

const PAGE_SIZE = 30;

/**
 * @param {{id: number, title: string}} vocabulary
 * @returns {void}
 */
export function openWordSheet(vocabulary) {
  const previousFocus = document.activeElement;
  const list = h("div", { class: "space-y-2" });
  const footer = h("div", { class: "pt-2" });
  let page = 0;
  let loading = false;

  const close = () => {
    stopSpeaking(); // 시트를 닫으면 재생 중인 발음도 멈춘다
    document.removeEventListener("keydown", onKey);
    overlay.remove();
    previousFocus?.focus?.();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
  };

  async function loadMore() {
    if (loading) return;
    loading = true;
    footer.replaceChildren(h("p", { class: "text-sm text-zinc-500", "aria-busy": "true" }, "불러오는 중…"));
    try {
      const data = await api(`/vocabularies/${vocabulary.id}/words`, { query: { page: page + 1, size: PAGE_SIZE } });
      page += 1;
      list.append(...data.items.map(wordRow));
      const more = page * PAGE_SIZE < data.total;
      footer.replaceChildren(more ? button({ variant: "secondary", full: true, onClick: loadMore }, `더 보기 (${list.children.length}/${data.total})`) : h("p", { class: "text-center text-sm text-zinc-500" }, `전체 ${data.total}단어`));
    } catch (error) {
      footer.replaceChildren(h("p", { class: "text-sm text-red-600" }, error?.detail ?? "불러오지 못했어요."), button({ variant: "secondary", onClick: loadMore }, "다시 시도"));
    } finally {
      loading = false;
      refreshIcons();
    }
  }

  const panel = h(
    "div",
    { class: "surface w-full max-w-lg overflow-y-auto rounded-b-none p-4", role: "dialog", "aria-modal": "true", "aria-label": `${vocabulary.title} 미리보기`, style: "max-height: 80dvh; padding-bottom: max(1rem, env(safe-area-inset-bottom))" },
    h("div", { class: "mb-3 flex items-center justify-between gap-2" }, h("h2", { class: "min-w-0 truncate text-lg font-bold text-zinc-900" }, vocabulary.title), button({ variant: "ghost", "aria-label": "닫기", onClick: close }, icon("x", "h-5 w-5"))),
    list,
    footer,
  );
  const overlay = h("div", { class: "fixed inset-0 z-50 flex items-end justify-center", style: "background: rgba(0, 0, 0, 0.4)", onclick: (event) => event.target === overlay && close() }, panel);
  document.body.append(overlay);
  document.addEventListener("keydown", onKey);
  refreshIcons();
  loadMore();
  panel.querySelector("button")?.focus();
}

/** @param {{term: string, meaning: string, example: string|null}} word */
function wordRow(word) {
  return h(
    "div",
    { class: "flex items-start gap-2 rounded-xl bg-zinc-50 px-3 py-2" },
    h(
      "div",
      { class: "min-w-0 flex-1" },
      h("p", { class: "text-base font-semibold text-zinc-900" }, word.term),
      h("p", { class: "text-sm text-zinc-700" }, word.meaning),
      word.example ? h("p", { class: "mt-1 text-xs text-zinc-500" }, word.example) : null,
    ),
    h(
      "div",
      { class: "flex shrink-0 items-center" },
      speakButton({ text: word.term, kind: "word", key: `word:${word.term}` }),
      word.example ? speakButton({ text: word.example, kind: "sentence", key: `sentence:${word.term}` }) : null,
    ),
  );
}
