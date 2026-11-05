/*
 * 2026-11-05 - voda-voca - 발음 듣기 버튼: 단어/예문 재생, 재생 중 표시(is-playing), 44px 터치 타깃 (v2.2 TTS, REQ-125)
 * 파일 위치: src/frontend/js/views/components/speak-button.js
 */

import { bindSpeakState, speakAriaLabel } from "../../core/speak-model.js";
import { getSpeakingState, speakSentence, speakWord, subscribeSpeaking } from "../../core/tts.js";
import { h, icon } from "../../core/dom.js";

/**
 * 누르면 텍스트를 읽어 주는 아이콘 버튼. 재생 중에는 같은 key 의 버튼만 강조된다.
 * 소리는 반드시 이 버튼의 클릭 핸들러 안에서만 낸다 (브라우저 자동재생 제한: 제스처 밖 호출은 not-allowed).
 * @param {{text: string, kind?: "word" | "sentence", key: string, label?: string}} opts
 * @returns {HTMLButtonElement}
 */
export function speakButton({ text, kind = "word", key, label }) {
  const play = kind === "sentence" ? speakSentence : speakWord;
  const el = /** @type {HTMLButtonElement} */ (
    h(
      "button",
      {
        type: "button",
        class: "btn btn-ghost btn-icon speak-btn focus-ring",
        "aria-label": label ?? speakAriaLabel(kind, text),
        "aria-pressed": "false",
        onclick: (event) => {
          event.stopPropagation(); // 플래시카드 뒷면에 있어도 카드가 뒤집히지 않게
          play(text, key);
        },
      },
      icon("volume-2", "h-5 w-5"),
    )
  );
  bindSpeakState({
    subscribe: subscribeSpeaking,
    getState: getSpeakingState,
    key,
    isConnected: () => el.isConnected,
    apply: ({ playing, ariaPressed }) => {
      el.classList.toggle("is-playing", playing);
      el.setAttribute("aria-pressed", ariaPressed);
    },
  });
  return el;
}
