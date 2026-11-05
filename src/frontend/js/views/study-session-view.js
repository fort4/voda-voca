/*
 * 2026-11-05 - voda-voca - 집중 학습 세션 화면: 한 화면에 한 문항, 퀴즈(4지선다)와 플래시카드(알아요/헷갈려요), 즉시 피드백 시트
 * 파일 위치: src/frontend/js/views/study-session-view.js
 */

import { api } from "../core/api.js";
import { button, clear, h, notice, refreshIcons, skeleton } from "../core/dom.js";
import { createSessionDriver } from "../core/session-driver.js";
import { ACTION, PHASE, currentItem, progressOf, summaryOf } from "../core/session-runner.js";
import { VIEW_ACTION, choiceStates, errorCopy, sessionKeyAction } from "../core/session-view-model.js";
import { isButtonTarget, modalIsOpen, shortcutsBlocked } from "../core/shortcuts.js";
import { playCorrect } from "../core/sound.js";
import { confirmDialog } from "../core/toast.js";
import { speak } from "../core/tts.js";
import { renderFeedbackSheet } from "./components/feedback-sheet.js";
import { renderProgressHeader } from "./components/progress-header.js";
import { renderSessionResult } from "./components/session-result.js";

/**
 * @param {HTMLElement} root
 * @param {{query: Record<string, string>, navigate: (path: string) => void}} ctx
 * @returns {() => void} 화면을 떠날 때의 정리 함수
 */
export function studySessionView(root, ctx) {
  const mode = ctx.query.mode === "flashcard" ? "flashcard" : "quiz";
  let flipped = false;
  let flipKey = "";
  let refs = { card: null, known: null, unsure: null };
  let advanceTimer = null;

  const driver = createSessionDriver({
    api,
    onChange: (state, action) => {
      const key = `${state.sessionId}:${state.index}`;
      if (key !== flipKey) {
        flipKey = key;
        flipped = false;
      }
      if (action.type === ACTION.ANSWER_RECEIVED && state.feedback?.is_correct) playCorrect();
      paint(state);
      // 플래시카드는 시트 없이 바로 다음 카드로 간다 (속도 우선)
      if (state.phase === PHASE.FEEDBACK_SHOWING && state.mode === "flashcard") {
        advanceTimer = setTimeout(() => driver.dispatch({ type: ACTION.NEXT }), 0);
      }
    },
  });

  /** 상태 머신 액션과 화면 전용 행동을 한 곳에서 처리한다. */
  async function act(action) {
    switch (action.type) {
      case VIEW_ACTION.FLIP:
        flipped = !flipped;
        syncFlashcard();
        return;
      case VIEW_ACTION.REQUEST_ABORT: {
        const ok = await confirmDialog({ title: "학습을 중단할까요?", text: "푼 문항은 이미 저장되어 있어요.", confirmText: "중단" });
        if (ok) driver.dispatch({ type: ACTION.ABORT });
        return;
      }
      case VIEW_ACTION.GO_HOME:
        ctx.navigate("/");
        return;
      case VIEW_ACTION.GO_EXPLORE:
        ctx.navigate("/explore");
        return;
      case VIEW_ACTION.GO_REVIEW:
        ctx.navigate("/review");
        return;
      case ACTION.START:
        driver.dispatch({ ...action, mode: driver.getState().mode });
        return;
      default:
        driver.dispatch(action);
    }
  }

  function onKeydown(event) {
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    if (shortcutsBlocked({ target: event.target, modalOpen: modalIsOpen() })) return;
    if ((event.key === "Enter" || event.key === " ") && isButtonTarget(event.target)) return; // 브라우저가 그 버튼을 누른다
    const action = sessionKeyAction(event.key, driver.getState(), { flipped });
    if (!action) return;
    event.preventDefault();
    act(action);
  }

  // ----- 그리기 -----

  function paint(state) {
    clear(root);
    refs = { card: null, known: null, unsure: null };
    switch (state.phase) {
      case PHASE.LOADING:
        root.append(skeleton(3));
        break;
      case PHASE.QUESTION_ACTIVE:
      case PHASE.FEEDBACK_SHOWING:
        root.append(renderQuestion(state));
        break;
      case PHASE.SESSION_COMPLETE:
        root.append(
          renderSessionResult({
            summary: summaryOf(state),
            onRestart: () => act({ type: ACTION.START }),
            onHome: () => act({ type: VIEW_ACTION.GO_HOME }),
          }),
        );
        break;
      case PHASE.EXPIRED:
      case PHASE.ERROR:
        root.append(renderErrorNotice(state.error?.kind ?? "unknown", state.source));
        break;
      default:
        break;
    }
    refreshIcons();
    root.querySelector("[data-autofocus]")?.focus({ preventScroll: true });
  }

  function actionButtons(kind, source) {
    return h(
      "div",
      { class: "flex w-full flex-col gap-2 sm:flex-row sm:justify-center" },
      errorCopy(kind, { source }).actions.map((entry, index) =>
        button({ variant: index === 0 ? "primary" : "secondary", onClick: () => act(entry.action) }, entry.label),
      ),
    );
  }

  function renderErrorNotice(kind, source) {
    const copy = errorCopy(kind, { source });
    return notice({ iconName: copy.iconName, title: copy.title, text: copy.text, action: actionButtons(kind, source) });
  }

  function renderQuestion(state) {
    const item = currentItem(state);
    const sheetOpen = state.phase === PHASE.FEEDBACK_SHOWING && state.mode === "quiz";
    const speakTerm = () => speak(item.term);
    return h(
      "div",
      { class: `session-screen${sheetOpen ? " has-sheet" : ""}` },
      renderProgressHeader({
        progress: progressOf(state),
        onAbort: () => act({ type: VIEW_ACTION.REQUEST_ABORT }),
        onSpeak: speakTerm,
      }),
      state.mode === "flashcard" ? renderFlashcard(state, item) : renderQuizCard(item),
      state.error ? renderInlineError(state.error) : null,
      state.mode === "quiz" ? renderChoices(state, item) : renderFlashcardButtons(state),
      sheetOpen ? renderFeedbackSheet({ state, onNext: () => act({ type: ACTION.NEXT }), onSpeak: speak }) : null,
    );
  }

  function renderQuizCard(item) {
    return h(
      "section",
      { class: "session-card" },
      h("p", { class: "session-hint" }, "알맞은 뜻을 고르세요"),
      h("p", { class: "session-term" }, item.term),
      item.context ? h("p", { class: "session-context" }, item.context) : null,
    );
  }

  function renderChoices(state, item) {
    const states = choiceStates(state);
    const locked = state.phase !== PHASE.QUESTION_ACTIVE || Boolean(state.pending) || Boolean(state.error);
    return h(
      "div",
      { class: "choice-list", role: "group", "aria-label": "선택지" },
      item.options.map((option, index) =>
        h(
          "button",
          {
            type: "button",
            class: "choice-btn press focus-ring",
            "data-state": states[index] ?? "idle",
            disabled: locked,
            onclick: () => act({ type: ACTION.SUBMIT_ANSWER, choiceIndex: index }),
          },
          h("span", { class: "choice-no", "aria-hidden": "true" }, String(index + 1)),
          h("span", { class: "min-w-0 flex-1 break-words" }, option),
        ),
      ),
    );
  }

  function renderFlashcard(state, item) {
    const card = h(
      "div",
      { class: `flip-card${flipped ? " is-flipped" : ""}` },
      h("div", { class: "flip-face" }, h("p", { class: "session-hint" }, "탭해서 뒤집기"), h("p", { class: "session-term" }, item.term), item.context ? h("p", { class: "session-context" }, item.context) : null),
      h(
        "div",
        { class: "flip-face flip-back" },
        h("p", { class: "session-term" }, item.meaning),
        item.example_meaning ? h("p", { class: "session-context" }, item.example_meaning) : null,
      ),
    );
    refs.card = card;
    return h("div", { class: "flip-scene", role: "button", tabindex: "0", "aria-label": "카드 뒤집기", onclick: () => act({ type: VIEW_ACTION.FLIP }) }, card);
  }

  function renderFlashcardButtons(state) {
    const busy = state.phase !== PHASE.QUESTION_ACTIVE || Boolean(state.pending) || Boolean(state.error);
    refs.unsure = button({ variant: "secondary", full: true, disabled: busy || !flipped, onClick: () => act({ type: ACTION.EVALUATE_FLASHCARD, known: false }) }, "헷갈려요 (←)");
    refs.known = button({ variant: "primary", full: true, disabled: busy || !flipped, onClick: () => act({ type: ACTION.EVALUATE_FLASHCARD, known: true }) }, "알아요 (→)");
    refs.busy = busy;
    return h("div", { class: "grid grid-cols-2 gap-3" }, refs.unsure, refs.known);
  }

  /** 카드를 뒤집어도 화면을 다시 그리지 않는다 (뒤집기 애니메이션이 끊기지 않도록 클래스만 바꾼다). */
  function syncFlashcard() {
    refs.card?.classList.toggle("is-flipped", flipped);
    for (const control of [refs.known, refs.unsure]) if (control) control.disabled = refs.busy || !flipped;
  }

  function renderInlineError(error) {
    return h(
      "div",
      { class: "session-inline-error", role: "alert" },
      h("p", { class: "font-semibold" }, errorCopy(error.kind).title),
      h("p", {}, errorCopy(error.kind).text),
      actionButtons(error.kind),
    );
  }

  document.addEventListener("keydown", onKeydown);
  driver.dispatch({ type: ACTION.START, mode, source: ctx.query.source, includeMemorized: ctx.query.include_memorized === "1" });

  return () => {
    document.removeEventListener("keydown", onKeydown);
    clearTimeout(advanceTimer);
    driver.dispose();
  };
}
