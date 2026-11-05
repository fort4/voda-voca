/*
 * 2026-11-05 - voda-voca - 음성 읽기(TTS) 래퍼: Web Speech API, 보이스 자동 선택(en-US > en-GB > en-*), 단어/문장 프리셋, 재생 상태 구독, 연속 클릭 방어, 오류 분류 (v1.1 Phase 1, v2.2 확장)
 * 파일 위치: src/frontend/js/core/tts.js
 */

export const TTS_DEFAULTS = Object.freeze({ lang: "en-US", rate: 0.9, pitch: 1.0 });

/** 예문은 단어보다 조금 느리게 읽는다 (REQ-125 의 0.9 는 표제어 기준). */
export const SENTENCE_RATE = 0.85;

/** 선호 언어 순서. 이 순서로 찾고, 없으면 en-* 아무 보이스. */
export const PREFERRED_LANGS = Object.freeze(["en-US", "en-GB"]);

/** 언어 표기를 비교용으로 맞춘다. Android 는 "en_US" 를 쓴다. */
const normalizeLang = (lang) => String(lang ?? "").replace(/_/g, "-").toLowerCase();

/** utterance.lang 에는 BCP-47 표기(en-US)를 쓴다. 보이스가 "en_US" 로 알려 줘도 하이픈으로 바꾼다. */
const toBcp47 = (lang) => String(lang).replace(/_/g, "-");

/** "en" 또는 "en-XX" 만 영어로 본다. "enx-ZZ" 같은 다른 언어 코드는 제외. */
const isEnglish = (lang) => lang === "en" || lang.startsWith("en-");

/**
 * 재생할 보이스를 고른다 (순수 함수).
 * 선호 언어(en-US → en-GB) 순으로 찾고, 같은 언어 안에서는 localService(오프라인 가능) 보이스를 먼저 쓴다.
 * 선호 언어가 없으면 아무 영어(en-*) 보이스, 영어가 전혀 없으면 null.
 * @param {ArrayLike<{lang: string, localService?: boolean}> | null | undefined} voices
 * @param {readonly string[]} [preferred]
 * @returns {any | null}
 */
export function pickVoice(voices, preferred = PREFERRED_LANGS) {
  const list = Array.from(voices ?? []).filter((voice) => voice && typeof voice.lang === "string");
  const best = (candidates) => candidates.find((voice) => voice.localService) ?? candidates[0] ?? null;
  for (const lang of preferred) {
    const found = best(list.filter((voice) => normalizeLang(voice.lang) === normalizeLang(lang)));
    if (found) return found;
  }
  return best(list.filter((voice) => isEnglish(normalizeLang(voice.lang))));
}

/** 사용자에게 알려야 하는 재생 불가 사유 → 안내 문구 */
const NOTICE_MESSAGES = Object.freeze({
  blocked: "브라우저가 소리 재생을 막았어요. 버튼을 다시 눌러 보세요.",
  "no-voice": "이 기기에는 영어 음성이 없어 발음이 정확하지 않을 수 있어요.",
  unsupported: "이 브라우저는 발음 듣기를 지원하지 않아요.",
});

/**
 * @param {string} reason "blocked" | "no-voice" | "unsupported"
 * @returns {string} 토스트에 쓸 한글 문구
 */
export function noticeMessage(reason) {
  return NOTICE_MESSAGES[reason] ?? "발음을 재생하지 못했어요.";
}

/** cancel() 이나 새 발화가 이전 발화를 끊을 때 브라우저가 보내는 오류. 정상 종료로 본다. */
const NORMAL_END_ERRORS = new Set(["interrupted", "canceled"]);

/**
 * @typedef {{status: "idle" | "speaking", key: string | null}} SpeakingState
 */

/**
 * 음성 합성기 래퍼를 만든다. 테스트에서는 synth 와 Utterance 를 주입한다.
 * @param {{synth?: any, UtteranceCtor?: any, warn?: (msg: string, err?: unknown) => void, notify?: ((reason: string) => void) | null, defaults?: typeof TTS_DEFAULTS}} [opts]
 */
export function createSpeaker({
  synth = globalThis.speechSynthesis,
  UtteranceCtor = globalThis.SpeechSynthesisUtterance,
  warn = (msg, err) => console.warn(msg, err ?? ""),
  notify = null,
  defaults = TTS_DEFAULTS,
} = {}) {
  let warnedUnsupported = false;
  let voices = [];
  /** @type {any} */
  let voice = null;
  /** @type {SpeakingState} */
  let state = { status: "idle", key: null };
  const listeners = new Set();
  /** 발화마다 올리는 번호. 이미 대체된 발화의 늦은 이벤트를 걸러 낸다. */
  let seq = 0;
  /** 진행 중 발화 참조. 일부 브라우저는 참조가 없으면 GC 되어 onend 가 오지 않는다. */
  let current = null;
  let notifier = notify;
  let noticeShown = false;

  const supported = () => Boolean(synth) && typeof UtteranceCtor === "function";

  /** 보이스 목록을 다시 읽어 고른다. 목록 조회 실패는 재생을 막지 않는다. */
  const refreshVoices = () => {
    try {
      voices = Array.from(synth?.getVoices?.() ?? []);
      voice = pickVoice(voices);
    } catch {
      voices = [];
      voice = null;
    }
  };
  if (synth) {
    refreshVoices();
    // Chrome 은 처음에 목록이 비어 있다가 voiceschanged 로 채운다.
    if (typeof synth.addEventListener === "function") synth.addEventListener("voiceschanged", refreshVoices);
    else synth.onvoiceschanged = refreshVoices;
  }

  /** 상태가 실제로 바뀔 때만 구독자에게 알린다. 구독자의 예외는 재생에 영향을 주지 않는다. */
  const setState = (/** @type {SpeakingState} */ next) => {
    if (next.status === state.status && next.key === state.key) return;
    state = next;
    for (const listener of [...listeners]) {
      try {
        listener({ ...state });
      } catch (error) {
        warn("재생 상태 구독자에서 오류가 났습니다.", error);
      }
    }
  };

  /** 재생 불가 사유를 사용자에게 알린다. 학습 세션당 한 번(resetNotice 로 초기화). */
  const noticeOnce = (/** @type {string} */ reason) => {
    if (noticeShown) return;
    noticeShown = true;
    try {
      notifier?.(reason);
    } catch (error) {
      warn("안내를 표시하지 못했습니다.", error);
    }
  };

  /**
   * @param {string} text
   * @param {{lang?: string, rate?: number, pitch?: number}} overrides
   * @param {string | null} key 어떤 버튼이 재생 중인지 구분하는 식별자
   */
  const start = (text, overrides, key) => {
    const spoken = typeof text === "string" ? text.trim() : "";
    if (!spoken) return false;
    if (!supported()) {
      if (!warnedUnsupported) {
        warnedUnsupported = true;
        warn("이 브라우저는 음성 읽기(Web Speech API)를 지원하지 않습니다.");
      }
      noticeOnce("unsupported");
      return false;
    }
    try {
      if (!voice) refreshVoices(); // voiceschanged 를 안 주는 브라우저(Safari 등)를 위해 다시 읽는다
      // 목록은 채워졌는데 영어가 없을 때만 알린다. 목록이 비어 있으면 아직 로딩 중일 수 있다.
      if (voices.length > 0 && !voice) noticeOnce("no-voice");

      const mine = ++seq;
      synth.cancel(); // 연속 클릭 시 이전 발화를 끊고 새로 읽는다 (이전 발화의 interrupted 는 seq 로 걸러진다)
      const utterance = new UtteranceCtor(spoken);
      if (voice) utterance.voice = voice;
      utterance.lang = overrides.lang ?? (voice ? toBcp47(voice.lang) : defaults.lang);
      utterance.rate = overrides.rate ?? defaults.rate;
      utterance.pitch = overrides.pitch ?? defaults.pitch;
      utterance.onstart = () => {
        if (mine === seq) setState({ status: "speaking", key });
      };
      utterance.onend = () => {
        if (mine !== seq) return;
        current = null;
        setState({ status: "idle", key: null });
      };
      utterance.onerror = (event) => {
        const error = event?.error;
        if (mine === seq) {
          current = null;
          setState({ status: "idle", key: null });
        }
        if (NORMAL_END_ERRORS.has(error)) return;
        if (error === "not-allowed") noticeOnce("blocked");
        warn("음성 읽기에 실패했습니다.", error);
      };
      current = utterance;
      setState({ status: "speaking", key }); // 옵티미스틱: onstart 를 기다리지 않아 연타해도 깜박이지 않는다
      synth.speak(utterance);
      return true;
    } catch (error) {
      current = null;
      setState({ status: "idle", key: null });
      warn("음성 읽기를 시작하지 못했습니다.", error);
      return false;
    }
  };

  /** 진행 중인 발화를 멈추고 즉시 idle 로 만든다. */
  const stop = () => {
    seq += 1;
    current = null;
    if (supported()) {
      try {
        synth.cancel();
      } catch (error) {
        warn("음성 읽기를 멈추지 못했습니다.", error);
      }
    }
    setState({ status: "idle", key: null });
  };

  return {
    isSupported: supported,

    /** 지금 고른 보이스 (없으면 null: 브라우저 기본 + lang 에 맡긴다). */
    getVoice: () => voice,

    /** 현재 재생 상태의 복사본 */
    getState: () => ({ ...state }),

    /**
     * 재생 상태가 바뀔 때마다 호출될 함수를 등록한다.
     * @param {(state: SpeakingState) => void} listener
     * @returns {() => void} 구독 해제 함수
     */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    /**
     * 텍스트를 소리 내어 읽는다. 이전 발화는 즉시 취소한다.
     * 빈 텍스트, 미지원 환경, 합성 오류는 false 를 돌려주고 예외를 던지지 않는다.
     * @param {string} text
     * @param {{lang?: string, rate?: number, pitch?: number}} [overrides]
     * @returns {boolean} 발화를 시작했는지
     */
    speak: (text, overrides = {}) => start(text, overrides, null),

    /** 표제어를 읽는다 (속도 0.9). @param {string} text @param {string} [key] */
    speakWord: (text, key = null) => start(text, { rate: defaults.rate }, key),

    /** 예문을 읽는다 (속도 0.85). @param {string} text @param {string} [key] */
    speakSentence: (text, key = null) => start(text, { rate: SENTENCE_RATE }, key),

    stop,
    /** stop 의 이전 이름 (기존 호출처 호환) */
    cancel: stop,

    /** 안내 함수를 나중에 연결한다 (토스트 등). 코어는 UI 를 모른다. @param {((reason: string) => void) | null} fn */
    setNotifier(fn) {
      notifier = fn;
    },

    /** 새 학습 세션이 시작될 때 불러, 세션당 1회 안내를 다시 허용한다. */
    resetNotice() {
      noticeShown = false;
    },
  };
}

/** 앱 전역에서 쓰는 기본 인스턴스 */
export const speaker = createSpeaker();

/** @param {string} text @returns {boolean} */
export function speak(text) {
  return speaker.speak(text);
}
/** @param {string} text @param {string} [key] @returns {boolean} */
export const speakWord = (text, key) => speaker.speakWord(text, key);
/** @param {string} text @param {string} [key] @returns {boolean} */
export const speakSentence = (text, key) => speaker.speakSentence(text, key);
export const stopSpeaking = () => speaker.stop();
/** @param {(state: SpeakingState) => void} listener @returns {() => void} */
export const subscribeSpeaking = (listener) => speaker.subscribe(listener);
export const getSpeakingState = () => speaker.getState();
/** @param {((reason: string) => void) | null} fn */
export const setSpeechNotifier = (fn) => speaker.setNotifier(fn);
export const resetSpeechNotice = () => speaker.resetNotice();
