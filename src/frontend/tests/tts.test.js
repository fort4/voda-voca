/*
 * 2026-11-02 - voda-voca - TTS 래퍼 단위 테스트: 파라미터 매핑과 기본값, 이전 발화 취소, 빈 입력·미지원·합성 오류 가드 (v1.1)
 * 파일 위치: src/frontend/tests/tts.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createSpeaker, TTS_DEFAULTS } from "../js/core/tts.js";

class FakeUtterance {
  constructor(text) {
    this.text = text;
    this.lang = undefined;
    this.rate = undefined;
    this.pitch = undefined;
    this.onerror = null;
  }
}

function fakeSynth() {
  const log = [];
  return {
    log,
    speak(u) {
      log.push(["speak", u]);
    },
    cancel() {
      log.push(["cancel"]);
    },
  };
}

test("기본 설정은 en-US, 속도 0.9, 음높이 1.0 이다", () => {
  assert.deepEqual({ ...TTS_DEFAULTS }, { lang: "en-US", rate: 0.9, pitch: 1.0 });
});

test("speak 은 표제어를 발화 객체에 매핑하고 기본 설정을 적용한다", () => {
  const synth = fakeSynth();
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} });
  assert.equal(speaker.speak("  apple "), true);
  const [, utterance] = synth.log.at(-1);
  assert.equal(utterance.text, "apple", "앞뒤 공백을 뺀다");
  assert.equal(utterance.lang, "en-US");
  assert.equal(utterance.rate, 0.9);
  assert.equal(utterance.pitch, 1.0);
});

test("호출마다 이전 발화를 먼저 취소하고 새로 읽는다 (연속 클릭)", () => {
  const synth = fakeSynth();
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} });
  speaker.speak("apple");
  speaker.speak("banana");
  assert.deepEqual(synth.log.map((entry) => entry[0]), ["cancel", "speak", "cancel", "speak"]);
});

test("재정의 옵션은 기본값보다 우선한다", () => {
  const synth = fakeSynth();
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} });
  speaker.speak("hello", { rate: 1.2, lang: "en-GB" });
  const [, utterance] = synth.log.at(-1);
  assert.equal(utterance.rate, 1.2);
  assert.equal(utterance.lang, "en-GB");
  assert.equal(utterance.pitch, 1.0);
});

test("빈 텍스트나 공백만 있는 텍스트는 아무것도 하지 않는다", () => {
  const synth = fakeSynth();
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} });
  assert.equal(speaker.speak(""), false);
  assert.equal(speaker.speak("   "), false);
  assert.equal(speaker.speak(null), false);
  assert.equal(synth.log.length, 0);
});

test("미지원 환경에서는 예외 없이 false 를 돌려주고, 경고는 한 번만 한다", () => {
  const warnings = [];
  const speaker = createSpeaker({ synth: undefined, UtteranceCtor: undefined, warn: (m) => warnings.push(m) });
  assert.equal(speaker.isSupported(), false);
  assert.doesNotThrow(() => speaker.speak("apple"));
  assert.equal(speaker.speak("banana"), false);
  assert.equal(warnings.length, 1);
});

test("합성기가 예외를 던져도 조용히 false 를 돌려준다", () => {
  const warnings = [];
  const synth = { cancel() {}, speak() { throw new Error("boom"); } };
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: (m) => warnings.push(m) });
  assert.equal(speaker.speak("apple"), false);
  assert.equal(warnings.length, 1);
});

test("발화 오류(예: 오프라인 음성 없음)는 onerror 에서 경고만 남긴다", () => {
  const warnings = [];
  const synth = fakeSynth();
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: (m, e) => warnings.push([m, e]) });
  speaker.speak("apple");
  const [, utterance] = synth.log.at(-1);
  assert.equal(typeof utterance.onerror, "function");
  utterance.onerror({ error: "network" });
  assert.equal(warnings[0][1], "network");
});

test("cancel 은 합성기의 cancel 을 부르고, 미지원이면 아무 일도 없다", () => {
  const synth = fakeSynth();
  createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} }).cancel();
  assert.deepEqual(synth.log, [["cancel"]]);
  assert.doesNotThrow(() => createSpeaker({ synth: undefined, UtteranceCtor: undefined, warn: () => {} }).cancel());
});
