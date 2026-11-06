/*
 * 2026-11-05 - voda-voca - 즉시 피드백 하단 시트: 정오답, 뜻, 예문과 해석, 발음 듣기, 다음 버튼 (아래에서 올라온다)
 * 파일 위치: src/frontend/js/views/components/feedback-sheet.js
 */

import { button, h, icon, kbdHint } from "../../core/dom.js";
import { phoneticLine } from "./phonetic-line.js";
import { speakButton } from "./speak-button.js";
import { feedbackTone } from "../../core/session-view-model.js";

/**
 * 해설 시트를 만든다. 맨 아래에 고정되고 200ms 트랜지션으로 올라온다 (prefers-reduced-motion 이면 즉시).
 * @param {{state: object, onNext: () => void}} opts
 * @returns {HTMLElement|null} 해설을 보여 줄 상태가 아니면 null
 */
export function renderFeedbackSheet({ state, onNext }) {
  const tone = feedbackTone(state);
  if (!tone) return null;
  const { feedback } = state;

  const sheet = h(
    "section",
    { class: `feedback-sheet feedback-sheet--${tone.tone}`, role: "status", "aria-live": "assertive" },
    h(
      "div",
      { class: "flex flex-wrap items-center gap-2" },
      h("h2", { class: "text-xl font-extrabold tracking-tight" }, tone.title),
      tone.badge ? h("span", { class: "sheet-pill" }, icon("sparkles", "h-3.5 w-3.5"), tone.badge) : null,
      tone.streakText ? h("span", { class: "sheet-pill" }, tone.streakText) : null,
    ),
    h(
      "div",
      { class: "sheet-body mt-3 space-y-1" },
      h(
        "p",
        { class: "flex flex-wrap items-center gap-x-2 text-lg font-bold" },
        h("span", { class: "break-words" }, feedback.term),
        phoneticLine(feedback.phonetic),
        speakButton({ text: feedback.term, kind: "word", key: `word:${feedback.term}` }),
      ),
      h("p", { class: "break-words text-base font-semibold" }, feedback.meaning),
      feedback.example
        ? h(
            "div",
            { class: "flex items-start gap-1" },
            h("p", { class: "sheet-sub min-w-0 flex-1 break-words pt-1 text-body italic leading-relaxed" }, feedback.example),
            speakButton({ text: feedback.example, kind: "sentence", key: `sentence:${feedback.term}` }),
          )
        : null,
      feedback.example_meaning ? h("p", { class: "sheet-sub break-words text-sm leading-relaxed" }, feedback.example_meaning) : null,
    ),
    h("div", { class: "mt-4" }, button({ variant: "primary", full: true, onClick: onNext, "data-autofocus": "true" }, tone.buttonLabel, kbdHint("Enter"))),
  );
  // 다음 프레임에 열어야 translateY(100%) → 0 트랜지션이 보인다.
  requestAnimationFrame(() => sheet.classList.add("is-open"));
  return sheet;
}
