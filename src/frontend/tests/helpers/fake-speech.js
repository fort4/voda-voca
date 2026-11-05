/*
 * 2026-11-05 - voda-voca - Web Speech API 테스트용 목: 이벤트를 테스트가 하나씩 발생시켜 TTS 상태 전이를 결정적으로 검증한다 (v2.2 TTS)
 * 파일 위치: src/frontend/tests/helpers/fake-speech.js
 */

/** 브라우저의 SpeechSynthesisUtterance 를 흉내 낸다. 이벤트 슬롯은 TTS 래퍼가 채운다. */
export class FakeUtterance {
  constructor(text) {
    this.text = text;
    this.lang = undefined;
    this.rate = undefined;
    this.pitch = undefined;
    this.voice = undefined;
    this.onstart = null;
    this.onend = null;
    this.onerror = null;
  }
}

/**
 * SpeechSynthesisVoice 모양의 객체.
 * @param {string} name
 * @param {string} lang 예: "en-US", Android 식 "en_US"
 * @param {boolean} [localService]
 */
export function fakeVoice(name, lang, localService = false) {
  return { name, lang, localService, default: false, voiceURI: name };
}

/**
 * speechSynthesis 를 흉내 낸다. speak() 는 발화를 대기시킬 뿐 스스로 끝내지 않으며,
 * 테스트가 start()/finish()/fail() 로 이벤트를 발생시킨다. cancel() 은 실제 브라우저처럼
 * 진행 중인 발화에 error "interrupted" 를 보낸다. 타이머를 쓰지 않는다.
 */
export class FakeSynth {
  /** @param {{voices?: any[]}} [opts] */
  constructor({ voices = [] } = {}) {
    this.log = [];
    this.current = null;
    this._voices = [...voices];
    this._listeners = new Set();
  }

  speak(utterance) {
    this.log.push(["speak", utterance]);
    this.current = utterance;
  }

  cancel() {
    this.log.push(["cancel"]);
    const utterance = this.current;
    this.current = null;
    utterance?.onerror?.({ error: "interrupted" });
  }

  getVoices() {
    return [...this._voices];
  }

  addEventListener(type, listener) {
    if (type === "voiceschanged") this._listeners.add(listener);
  }

  removeEventListener(type, listener) {
    if (type === "voiceschanged") this._listeners.delete(listener);
  }

  get voiceListenerCount() {
    return this._listeners.size;
  }

  // ----- 테스트가 쓰는 제어 -----

  /** 보이스 목록을 바꾼다. 브라우저처럼 voiceschanged 를 따로 발생시켜야 래퍼가 안다. */
  setVoices(voices) {
    this._voices = [...voices];
  }

  emitVoicesChanged() {
    for (const listener of [...this._listeners]) listener({ type: "voiceschanged" });
  }

  /** 현재 발화가 소리를 내기 시작했다. */
  start() {
    this.current?.onstart?.({});
  }

  /** 현재 발화가 끝까지 재생됐다. */
  finish() {
    const utterance = this.current;
    this.current = null;
    utterance?.onend?.({});
  }

  /** 현재 발화가 오류로 끝났다. @param {string} error 예: "not-allowed" */
  fail(error) {
    const utterance = this.current;
    this.current = null;
    utterance?.onerror?.({ error });
  }

  /** 마지막으로 speak 된 발화 */
  get lastUtterance() {
    const last = [...this.log].reverse().find((entry) => entry[0] === "speak");
    return last ? last[1] : null;
  }

  /** 호출 이름만 모은 기록. 예: ["cancel", "speak"] */
  get calls() {
    return this.log.map((entry) => entry[0]);
  }
}
