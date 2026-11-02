/*
 * 2026-11-02 - voda-voca - 음성 읽기(TTS) 래퍼: Web Speech API, 연속 클릭 시 이전 발화 취소, 미지원·오류는 조용히 무시 (v1.1 Phase 1)
 * 파일 위치: src/frontend/js/core/tts.js
 */

export const TTS_DEFAULTS = Object.freeze({ lang: "en-US", rate: 0.9, pitch: 1.0 });

/**
 * 음성 합성기 래퍼를 만든다. 테스트에서는 synth 와 Utterance 를 주입한다.
 * @param {{synth?: any, UtteranceCtor?: any, warn?: (msg: string, err?: unknown) => void, defaults?: typeof TTS_DEFAULTS}} [opts]
 */
export function createSpeaker({
  synth = globalThis.speechSynthesis,
  UtteranceCtor = globalThis.SpeechSynthesisUtterance,
  warn = (msg, err) => console.warn(msg, err ?? ""),
  defaults = TTS_DEFAULTS,
} = {}) {
  let warnedUnsupported = false;

  const supported = () => Boolean(synth) && typeof UtteranceCtor === "function";

  return {
    isSupported: supported,

    /**
     * 텍스트를 소리 내어 읽는다. 이전 발화는 즉시 취소한다.
     * 빈 텍스트, 미지원 환경, 합성 오류는 false 를 돌려주고 예외를 던지지 않는다.
     * @param {string} text
     * @param {{lang?: string, rate?: number, pitch?: number}} [overrides]
     * @returns {boolean} 발화를 시작했는지
     */
    speak(text, overrides = {}) {
      const spoken = typeof text === "string" ? text.trim() : "";
      if (!spoken) return false;
      if (!supported()) {
        if (!warnedUnsupported) {
          warnedUnsupported = true;
          warn("이 브라우저는 음성 읽기(Web Speech API)를 지원하지 않습니다.");
        }
        return false;
      }
      try {
        synth.cancel(); // 연속 클릭 시 이전 발화를 끊고 새로 읽는다
        const utterance = new UtteranceCtor(spoken);
        utterance.lang = overrides.lang ?? defaults.lang;
        utterance.rate = overrides.rate ?? defaults.rate;
        utterance.pitch = overrides.pitch ?? defaults.pitch;
        utterance.onerror = (event) => warn("음성 읽기에 실패했습니다.", event?.error);
        synth.speak(utterance);
        return true;
      } catch (error) {
        warn("음성 읽기를 시작하지 못했습니다.", error);
        return false;
      }
    },

    /** 진행 중인 발화를 멈춘다. */
    cancel() {
      if (supported()) synth.cancel();
    },
  };
}

/** 앱 전역에서 쓰는 기본 인스턴스 */
export const speaker = createSpeaker();

/**
 * @param {string} text
 * @returns {boolean}
 */
export function speak(text) {
  return speaker.speak(text);
}
