/*
 * 2026-11-26 - voda-voca - 퀴즈 채점 직후 정답 영단어 자동 발음: 효과음이 끝난 뒤 재생, 효과음을 끄면 함께 끔 (DOM 없는 로직)
 * 파일 위치: src/frontend/js/core/answer-speech.js
 */

import { ACTION } from "./session-runner.js";
import { CUES, isMuted } from "./sound.js";
import { primeSpeech, speakWord } from "./tts.js";

/** 효과음이 끝나고 발음을 시작하기까지의 틈(ms). */
export const SPEECH_GAP_MS = 80;

/**
 * @param {string | null} name 효과음 큐 이름. 소리를 내지 않았으면 null
 * @returns {number} 그 큐가 울리는 길이(ms)
 */
export function cueDurationMs(name) {
  const cue = name ? CUES[/** @type {keyof typeof CUES} */ (name)] : null;
  return cue ? Math.round(Math.max(...cue.voices.map((voice) => voice.start + voice.duration)) * 1000) : 0;
}

/**
 * 테스트에서는 재생·음소거·타이머를 주입한다.
 * @param {{speak?: (text: string, key: string) => unknown, prime?: () => unknown, muted?: () => boolean, hidden?: () => boolean, schedule?: (fn: () => void, ms: number) => any, unschedule?: (id: any) => void}} [deps]
 */
export function createAnswerSpeech({
  speak = speakWord,
  prime = primeSpeech,
  muted = isMuted,
  hidden = () => globalThis.document?.hidden === true,
  schedule = (fn, ms) => setTimeout(fn, ms),
  unschedule = (id) => clearTimeout(id),
} = {}) {
  let timer = null;

  const cancel = () => {
    if (timer !== null) unschedule(timer);
    timer = null;
  };

  return {
    /** 답을 누르는 클릭·키 입력 안에서 부른다. 뒤이은 자동 재생을 브라우저가 막지 않게 준비한다. */
    unlock() {
      if (!muted()) prime();
    },

    /**
     * 퀴즈의 채점 응답이면 정답·오답과 관계없이 그 문항의 영단어를 읽는다.
     * @param {{mode: string, feedback?: {term?: string} | null}} state
     * @param {{type: string}} action
     * @param {string | null} playedCue 방금 소리를 낸 효과음 큐 이름
     */
    play(state, action, playedCue) {
      if (action.type !== ACTION.ANSWER_RECEIVED || state.mode !== "quiz" || muted()) return;
      const term = state.feedback?.term?.trim();
      if (!term) return;
      cancel();
      const delay = playedCue ? cueDurationMs(playedCue) + SPEECH_GAP_MS : 0;
      timer = schedule(() => {
        timer = null;
        if (!muted() && !hidden()) speak(term, `word:${term}`); // 기다리는 사이에 끄거나 탭을 벗어났을 수 있다
      }, delay);
    },

    /** 예약해 둔 발음을 취소한다. */
    cancel,
  };
}
