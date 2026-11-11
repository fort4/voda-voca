/*
 * 2026-11-05 - voda-voca - 집중 학습 세션 화면: 한 화면에 한 문항, 퀴즈(4지선다)와 플래시카드(알아요/헷갈려요), 즉시 피드백 시트
 * 파일 위치: src/frontend/js/views/study-session-view.js
 */

import { api } from "../core/api.js";
import { button, clear, h, kbdHint, notice, refreshIcons, skeleton } from "../core/dom.js";
import { createSessionDriver } from "../core/session-driver.js";
import { ACTION, PHASE, currentItem, progressOf, summaryOf } from "../core/session-runner.js";
import { VIEW_ACTION, choiceStates, errorCopy, flashcardFaces, sessionKeyAction } from "../core/session-view-model.js";
import { isButtonTarget, modalIsOpen, shortcutsBlocked } from "../core/shortcuts.js";
import { badgeView, soundCueFor } from "../core/combo-model.js";
import { playCue } from "../core/sound.js";
import { createBookmarkStore } from "../core/bookmark-store.js";
import { confirmDialog, toast } from "../core/toast.js";
import { resetSpeechNotice, stopSpeaking } from "../core/tts.js";
import { bookmarkButton } from "./components/bookmark-button.js";
import { renderComboRow } from "./components/combo-badge.js";
import { renderFeedbackSheet } from "./components/feedback-sheet.js";
import { renderProgressHeader } from "./components/progress-header.js";
import { phoneticLine } from "./components/phonetic-line.js";
import { posTag } from "./components/pos-tag.js";
import { renderSessionResult } from "./components/session-result.js";
import { speakButton } from "./components/speak-button.js";

/** CSS 의 card-exit-* 애니메이션 길이(ms)와 같아야 한다 */
const CARD_EXIT_MS = 180;

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
  // 플래시카드 전환 연출: 평가 직후 현재 카드가 밀려 나가고(leaving), 다음 카드는 한 번만 들어온다(enteredKey).
  let leaving = null; // { dir: "known"|"unsure", until: number } | null
  let enteredKey = "";
  let paintTimer = null;
  // 콤보 뱃지: 직전에 그린 콤보 값. 화면은 상태가 바뀔 때마다 다시 그려지므로, 늘어난 렌더에서만 바운스한다.
  let shownCombo = 0;
  // 완료 팡파레는 세션당 한 번만
  let completedSessionId = null;
  // 북마크: 사용자가 바꾼 값은 화면이 다시 그려져도 남도록 세션 화면 단위로 보관한다
  const bookmarks = createBookmarkStore({ api });
  const bookmarkFor = (item) =>
    h(
      "div",
      { class: "bookmark-slot" },
      bookmarkButton({ wordId: item.word_id, term: item.term, store: bookmarks, onError: () => toast("북마크를 바꾸지 못했어요. 잠시 후 다시 시도해 주세요.", "error") }),
    );

  const driver = createSessionDriver({
    api,
    onChange: (state, action) => {
      const key = `${state.sessionId}:${state.index}`;
      if (key !== flipKey) {
        flipKey = key;
        flipped = false;
        leaving = null;
        stopSpeaking(); // 문항이 바뀌면 이전 문항의 발음을 끊는다
      }
      if (action.type === ACTION.NEXT || action.type === ACTION.ABORT) stopSpeaking(); // 시트를 닫거나 세션을 중단할 때
      if (state.error) leaving = null; // 전송 실패 시 카드를 다시 보여 준다
      playCueFor(state, action);
      // 나가는 카드는 연출이 끝날 때까지 그대로 두고, 끝나면 서버 응답을 기다리지 않고 다음 카드를 미리 보여 준다
      clearTimeout(paintTimer);
      const remaining = leaving ? leaving.until - Date.now() : 0;
      if (remaining > 0) paintTimer = setTimeout(() => paint(driver.getState()), remaining);
      else paint(state);
      // 플래시카드는 시트 없이 바로 다음 카드로 간다 (속도 우선)
      if (state.phase === PHASE.FEEDBACK_SHOWING && state.mode === "flashcard") {
        // 나가는 연출이 끝난 뒤에 다음 카드로 넘어가 화면이 끊기지 않게 한다
        const wait = leaving ? Math.max(0, leaving.until - Date.now()) : 0;
        advanceTimer = setTimeout(() => driver.dispatch({ type: ACTION.NEXT }), wait);
      }
    },
  });

  /**
   * 효과음은 정책 함수(soundCueFor)가 정한다: 정답·마일스톤·오답(퀴즈만)·완료(정상 완주+정답 1개 이상).
   * 소리는 사용자가 답을 누르거나 결과를 보는 흐름 안에서만 난다.
   */
  function playCueFor(state, action) {
    let cue = null;
    if (action.type === ACTION.ANSWER_RECEIVED && state.feedback) {
      cue = soundCueFor({ type: "answer", mode: state.mode, isCorrect: state.feedback.is_correct === true, count: state.streak });
    } else if (state.phase === PHASE.SESSION_COMPLETE && completedSessionId !== state.sessionId) {
      completedSessionId = state.sessionId;
      const summary = summaryOf(state);
      cue = soundCueFor({ type: "complete", aborted: summary.aborted, answered: summary.answered, correct: summary.correct });
    }
    if (cue) playCue(cue);
  }

  /** 상태 머신 액션과 화면 전용 행동을 한 곳에서 처리한다. */
  async function act(action) {
    switch (action.type) {
      case VIEW_ACTION.FLIP:
        if (leaving) return; // 넘어가는 중에는 뒤집지 않는다
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
      case ACTION.EVALUATE_FLASHCARD:
        startLeaving(action.known);
        driver.dispatch(action);
        return;
      case ACTION.START:
        shownCombo = 0;
        resetSpeechNotice();
        driver.dispatch({ ...action, mode: driver.getState().mode });
        return;
      default:
        driver.dispatch(action);
    }
  }

  /** 평가한 카드를 알아요는 오른쪽, 헷갈려요는 왼쪽으로 밀어낸다. 요청이 오가며 화면이 다시 그려져도 사라진 채로 유지한다. */
  function startLeaving(known) {
    const state = driver.getState();
    if (state.mode !== "flashcard" || state.pending || leaving) return;
    leaving = { dir: known ? "known" : "unsure", until: Date.now() + CARD_EXIT_MS };
    refs.card?.parentElement?.classList.add(`card-exit-${leaving.dir}`);
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
    bookmarks.seed(state.items);
    const sheetOpen = state.phase === PHASE.FEEDBACK_SHOWING && state.mode === "quiz";
    const comboView = badgeView(shownCombo, state.streak);
    shownCombo = state.streak;
    return h(
      "div",
      { class: `session-screen${sheetOpen ? " has-sheet" : ""}` },
      renderProgressHeader({
        progress: progressOf(state),
        onAbort: () => act({ type: VIEW_ACTION.REQUEST_ABORT }),
        speakText: item.term,
      }),
      renderComboRow(comboView),
      state.mode === "flashcard" ? renderFlashcard(state, item) : renderQuizCard(item),
      state.error ? renderInlineError(state.error) : null,
      state.mode === "quiz" ? renderChoices(state, item) : renderFlashcardButtons(state),
      sheetOpen ? renderFeedbackSheet({ state, onNext: () => act({ type: ACTION.NEXT }) }) : null,
    );
  }

  function renderQuizCard(item) {
    const pos = posTag(item.pos);
    return h(
      "section",
      { class: "session-card" },
      bookmarkFor(item),
      h("p", { class: "session-hint" }, "알맞은 뜻을 고르세요"),
      h("p", { class: "session-term" }, item.term),
      // 품사는 문제 화면에도 보인다. 발음기호는 채점 후 해설 시트에서만 보인다 (서버가 출제 응답에서 null 로 막는다)
      pos ? h("p", { class: "session-meta" }, pos) : null,
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

  function renderFlashcard(state, current) {
    // 평가 직후에는 응답을 기다리는 동안에도 다음 카드를 앞면으로 미리 보여 준다 (카드가 사라졌다 튀어나오지 않게)
    const preview = leaving ? state.items[state.index + 1] ?? null : null;
    const item = preview ?? current;
    const faces = flashcardFaces(item);
    const card = h(
      "div",
      { class: `flip-card${flipped && !preview ? " is-flipped" : ""}` },
      h(
        "div",
        { class: "flip-face" },
        h("p", { class: "session-hint" }, "탭해서 뒤집기"),
        h("p", { class: "session-term" }, faces.front.term),
        // 앞면: 표제어 아래에 품사와 /발음기호/ 한 줄. 둘 다 없으면 줄 자체를 그리지 않는다
        faces.front.pos || faces.front.phonetic ? h("p", { class: "session-meta" }, posTag(faces.front.pos), phoneticLine(faces.front.phonetic)) : null,
      ),
      h(
        "div",
        { class: "flip-face flip-back" },
        h("p", { class: "session-term" }, faces.back.meaning),
        faces.back.example
          ? h(
              "div",
              { class: "flex items-center gap-1" },
              h("p", { class: "session-context" }, faces.back.example),
              speakButton({ text: faces.back.example, kind: "sentence", key: `sentence:${faces.front.term}` }),
            )
          : null,
        faces.back.exampleMeaning ? h("p", { class: "session-context" }, faces.back.exampleMeaning) : null,
      ),
    );
    refs.card = card;
    card.querySelector(".flip-back").inert = !(flipped && !preview); // 앞면일 땐 뒷면의 발음 버튼이 탭 순서에 끼지 않게
    let motion = "";
    const shownKey = preview ? `${state.sessionId}:${state.index + 1}` : flipKey;
    if (leaving && !preview) motion = " card-gone"; // 마지막 카드: 다음 카드가 없으니 결과 화면을 기다린다
    else if (shownKey !== enteredKey) {
      enteredKey = shownKey;
      motion = " card-enter";
    }
    const scene = h("div", { class: `flip-scene${motion}`, role: "button", tabindex: "0", "aria-label": "카드 뒤집기", onclick: () => act({ type: VIEW_ACTION.FLIP }) }, card);
    // 북마크 버튼은 뒤집히는 카드 밖(형제)에 둬서 앞·뒷면 모두 오른쪽 위에 보이고, 카드 전환 애니메이션에도 딸려 가지 않는다
    return h("div", { class: "flip-stage" }, scene, bookmarkFor(item));
  }

  function renderFlashcardButtons(state) {
    const busy = state.phase !== PHASE.QUESTION_ACTIVE || Boolean(state.pending) || Boolean(state.error);
    refs.unsure = button({ variant: "secondary", full: true, disabled: busy || !flipped, onClick: () => act({ type: ACTION.EVALUATE_FLASHCARD, known: false }) }, "헷갈려요", kbdHint("←"));
    refs.known = button({ variant: "primary", full: true, disabled: busy || !flipped, onClick: () => act({ type: ACTION.EVALUATE_FLASHCARD, known: true }) }, "알아요", kbdHint("→"));
    refs.busy = busy;
    return h("div", { class: "grid grid-cols-2 gap-3" }, refs.unsure, refs.known);
  }

  /** 카드를 뒤집어도 화면을 다시 그리지 않는다 (뒤집기 애니메이션이 끊기지 않도록 클래스만 바꾼다). */
  function syncFlashcard() {
    refs.card?.classList.toggle("is-flipped", flipped);
    const back = refs.card?.querySelector(".flip-back");
    if (back) back.inert = !flipped;
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
  resetSpeechNotice(); // 새 학습 세션: 재생 불가 안내를 다시 한 번 허용한다
  driver.dispatch({ type: ACTION.START, mode, source: ctx.query.source, includeMemorized: ctx.query.include_memorized === "1" });

  return () => {
    document.removeEventListener("keydown", onKeydown);
    clearTimeout(advanceTimer);
    clearTimeout(paintTimer);
    stopSpeaking(); // 화면을 떠나면 발음도 멈춘다
    driver.dispose();
  };
}
