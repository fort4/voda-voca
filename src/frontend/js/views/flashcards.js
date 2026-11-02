/*
 * 2026-11-02 - voda-voca - 플래시카드 화면: 3D 뒤집기, 좌우 스와이프, 키보드(←→, Space) 넘김, 셔플(현재 카드 유지) (REQ-012, REQ-013, REQ-019)
 * 파일 위치: src/frontend/js/views/flashcards.js
 */

import { api, ApiError } from "../core/api.js";
import { createDeck } from "../core/deck.js";
import { classifyGesture } from "../core/gesture.js";
import { button, clear, h, icon, notice, refreshIcons, skeleton } from "../core/dom.js";
import { parseStudySource, sourceFlashcardQuery } from "../lib/study-source.js";
import { speak } from "../core/tts.js";
import { isButtonTarget, modalIsOpen, shortcutsBlocked } from "../core/shortcuts.js";

export const FLASHCARD_LIMIT = 500;

function speakerButton(text, label, extraClass = "") {
  return h(
    "button",
    {
      type: "button",
      class: `press focus-ring inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-zinc-500 hover:bg-indigo-50 hover:text-indigo-600 ${extraClass}`,
      "aria-label": label,
      onclick: (e) => {
        e.stopPropagation();
        speak(text);
      },
    },
    icon("volume-2", "h-5 w-5"),
  );
}

/**
 * @param {HTMLElement} root
 * @param {{query: Record<string, string>, navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void}
 */
export function flashcardsView(root, { query, navigate }) {
  const source = parseStudySource(query);
  const controller = new AbortController();
  const state = { status: "loading", cards: [], deck: null, shuffle: false, error: "", done: false };
  const content = h("div", { class: "space-y-4" });
  root.append(content);

  if (!source) {
    content.append(
      notice({
        iconName: "book-open",
        title: "학습할 단어장을 고르지 않았습니다.",
        action: button({ variant: "secondary", onClick: () => navigate("/wordbooks") }, "단어장으로"),
      }),
    );
    return () => {};
  }

  /** 키보드 넘김. 입력 칸과 버튼에 포커스가 있으면 건드리지 않는다. */
  /** 단축키: ←/→ 이동, Space·Enter 뒤집기(버튼 포커스일 때는 브라우저 클릭에 맡김), S 셔플. 입력 칸과 모달에서는 무시. */
  function onKey(event) {
    if (shortcutsBlocked({ target: event.target, modalOpen: modalIsOpen() })) return;
    const key = event.key;
    if (key === "ArrowRight") {
      event.preventDefault();
      move("next");
    } else if (key === "ArrowLeft") {
      event.preventDefault();
      move("prev");
    } else if ((key === " " || key === "Enter") && !isButtonTarget(event.target)) {
      event.preventDefault();
      flip();
    } else if (key.toLowerCase() === "s" && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      if (state.status === "ok" && !state.done) setShuffle(!state.shuffle);
    }
  }
  document.addEventListener("keydown", onKey);

  async function load() {
    state.status = "loading";
    render();
    try {
      const data = await api("/study/flashcards", {
        query: { ...sourceFlashcardQuery(source), shuffle: false, limit: FLASHCARD_LIMIT },
        signal: controller.signal,
      });
      state.cards = data.items.map((item) => ({ term: item.term, meaning: item.meaning, example: item.example }));
      state.deck = createDeck(state.cards, { shuffle: state.shuffle });
      state.status = state.cards.length ? "ok" : "empty";
    } catch (error) {
      if (error.name === "AbortError") return;
      state.status = "error";
      state.error = error instanceof ApiError ? error.detail : "카드를 불러오지 못했습니다.";
    }
    render();
  }

  /** @param {"next"|"prev"} direction */
  function move(direction) {
    if (state.status !== "ok") return;
    if (direction === "next" && state.deck.atEnd()) {
      state.done = true;
      render();
      return;
    }
    if (direction === "next") state.deck.next();
    else state.deck.prev();
    state.done = false;
    render();
  }

  /** 뒤집기는 클래스만 바꿔 애니메이션이 끊기지 않게 한다. */
  function flip() {
    if (state.status !== "ok" || state.done) return;
    const flipped = state.deck.flip();
    const scene = content.querySelector(".flip-card");
    scene?.classList.toggle("is-flipped", flipped);
    scene?.setAttribute("aria-label", flipped ? "뜻 보기 (카드 앞면으로 돌리기)" : "뜻 보기 (카드 뒷면 보기)");
  }

  /** @param {boolean} on */
  function setShuffle(on) {
    state.shuffle = on;
    if (state.deck) state.deck.setShuffle(on);
    render();
  }

  function render() {
    clear(content);
    content.append(header());
    if (state.status === "loading") {
      content.append(skeleton(1));
    } else if (state.status === "error") {
      content.append(
        notice({
          iconName: "cloud-off",
          title: "카드를 불러오지 못했습니다.",
          text: state.error,
          action: button({ variant: "secondary", onClick: load }, "다시 시도"),
        }),
      );
    } else if (state.status === "empty") {
      content.append(
        notice({
          iconName: "book-open",
          title: "학습할 단어가 없습니다.",
          action: button({ variant: "secondary", onClick: () => navigate(source.kind === "wordbook" ? `/wordbooks/${source.wordbookId}` : "/bookmarks") }, "돌아가기"),
        }),
      );
    } else if (state.done) {
      content.append(
        notice({
          iconName: "check-circle",
          title: "모든 카드를 봤습니다.",
          action: h(
            "div",
            { class: "flex flex-wrap justify-center gap-2" },
            button({ onClick: restart }, "다시 보기"),
            button({ variant: "secondary", onClick: () => navigate(source.kind === "wordbook" ? `/wordbooks/${source.wordbookId}` : "/bookmarks") }, "목록으로"),
          ),
        }),
      );
    } else {
      content.append(cardArea());
    }
    refreshIcons();
  }

  function header() {
    const total = state.deck?.total ?? 0;
    const position = state.deck && total ? state.deck.position + 1 : 0;
    const percent = total ? Math.round((position / total) * 100) : 0;
    return h(
      "div",
      { class: "space-y-3" },
      h(
        "div",
        { class: "flex items-center gap-2" },
        button({ variant: "ghost", onClick: () => navigate(source.kind === "wordbook" ? `/wordbooks/${source.wordbookId}` : "/bookmarks") }, icon("x"), h("span", { class: "sr-only" }, "닫기")),
        h("h1", { class: "min-w-0 flex-1 text-lg font-bold" }, "플래시카드"),
        button(
          { variant: state.shuffle ? "primary" : "secondary", onClick: () => setShuffle(!state.shuffle), disabled: state.status !== "ok" },
          icon("shuffle"),
          h("span", { class: "text-sm" }, state.shuffle ? "셔플 켜짐" : "셔플"),
        ),
      ),
      total
        ? h(
            "div",
            { class: "space-y-1" },
            h("p", { class: "text-sm text-zinc-600" }, `${position} / ${total}`),
            h(
              "div",
              { class: "h-2 w-full overflow-hidden rounded-full bg-zinc-200", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(percent) },
              h("div", { class: "h-2 rounded-full bg-indigo-600 transition-all", style: `width: ${percent}%` }),
            ),
          )
        : null,
    );
  }

  function cardArea() {
    const card = state.deck.current();
    const flipped = state.deck.isFlipped();
    const sceneEl = h(
      "div",
      {
        class: "flip-scene touch-pan-y select-none",
        role: "button",
        tabindex: "0",
        "aria-label": flipped ? "뜻 보기 (카드 앞면으로 돌리기)" : "뜻 보기 (카드 뒷면 보기)",
        onpointerdown: (e) => { sceneEl.dataset.px = String(e.clientX); sceneEl.dataset.py = String(e.clientY); },
        onpointerup: (e) => {
          const dx = e.clientX - Number(sceneEl.dataset.px ?? e.clientX);
          const dy = e.clientY - Number(sceneEl.dataset.py ?? e.clientY);
          const gesture = classifyGesture(dx, dy);
          if (gesture === "tap") flip();
          else if (gesture === "next" || gesture === "prev") move(gesture);
        },
      },
      h(
        "div",
        { class: `flip-card relative min-h-[260px] w-full ${flipped ? "is-flipped" : ""}` },
        h(
          "div",
          { class: "flip-face" },
          h("span", { class: "break-words text-4xl font-bold text-zinc-900" }, card.term),
          h(
            "span",
            { class: "absolute right-3 top-3", onpointerdown: (e) => e.stopPropagation(), onpointerup: (e) => e.stopPropagation() },
            speakerButton(card.term, `${card.term} 발음 듣기`),
          ),
        ),
        h(
          "div",
          { class: "flip-face flip-back" },
          h("span", { class: "break-words text-2xl font-semibold text-zinc-900" }, card.meaning),
          card.example ? h("span", { class: "break-words text-base text-zinc-600" }, card.example) : null,
          card.example
            ? h(
                "span",
                { class: "absolute right-3 top-3", onpointerdown: (e) => e.stopPropagation(), onpointerup: (e) => e.stopPropagation() },
                speakerButton(card.example, "예문 발음 듣기"),
              )
            : null,
        ),
      ),
    );
    return h(
      "div",
      { class: "space-y-4" },
      sceneEl,
      h(
        "p",
        { class: "text-center text-sm text-zinc-500" },
        "카드를 탭하면 뒤집고, 좌우로 밀거나 ← → 키로 넘깁니다.",
      ),
      h(
        "div",
        { class: "grid grid-cols-3 gap-2" },
        button({ variant: "secondary", onClick: () => move("prev"), disabled: state.deck.position === 0 }, icon("chevron-left"), h("span", { class: "sr-only" }, "이전 카드")),
        button({ variant: "secondary", onClick: flip }, icon("rotate-cw"), h("span", { class: "text-sm" }, "뒤집기")),
        button({ onClick: () => move("next") }, icon("chevron-right"), h("span", { class: "sr-only" }, state.deck.atEnd() ? "마치기" : "다음 카드")),
      ),
    );
  }

  function restart() {
    state.deck = createDeck(state.cards, { shuffle: state.shuffle });
    state.done = false;
    render();
  }

  load();

  return () => {
    controller.abort();
    document.removeEventListener("keydown", onKey);
  };
}
