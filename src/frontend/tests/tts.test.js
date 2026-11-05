/*
 * 2026-11-02 - voda-voca - TTS 래퍼 단위 테스트: 파라미터 매핑과 기본값, 이전 발화 취소, 빈 입력·미지원·합성 오류 가드 (v1.1)
 * 파일 위치: src/frontend/tests/tts.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createSpeaker, pickVoice, TTS_DEFAULTS } from "../js/core/tts.js";
import { FakeSynth, FakeUtterance as HelperUtterance, fakeVoice } from "./helpers/fake-speech.js";

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

// ---------- v2.2 보이스 선택: en-US > en-GB > en-* (같은 언어 안에서는 localService 우선) ----------

test("pickVoice: 빈 목록이나 목록이 아닌 값은 null", () => {
  assert.equal(pickVoice([]), null);
  assert.equal(pickVoice(undefined), null);
  assert.equal(pickVoice(null), null);
});

test("pickVoice: en-US 가 en-GB 보다 우선한다 (목록 순서와 무관)", () => {
  const gb = fakeVoice("Daniel", "en-GB", true);
  const us = fakeVoice("Samantha", "en-US", false);
  assert.equal(pickVoice([gb, us]), us);
  assert.equal(pickVoice([us, gb]), us);
});

test("pickVoice: 같은 언어에서는 localService(오프라인 가능) 보이스를 먼저 고른다", () => {
  const cloud = fakeVoice("Google US English", "en-US", false);
  const local = fakeVoice("Samantha", "en-US", true);
  assert.equal(pickVoice([cloud, local]), local);
  assert.equal(pickVoice([local, cloud]), local);
});

test("pickVoice: en-US 가 없으면 en-GB, 그것도 없으면 아무 en-* 보이스", () => {
  const gb = fakeVoice("Daniel", "en-GB");
  const au = fakeVoice("Karen", "en-AU", true);
  const ko = fakeVoice("Yuna", "ko-KR", true);
  assert.equal(pickVoice([ko, au, gb]), gb);
  assert.equal(pickVoice([ko, au]), au, "en-* 폴백");
  assert.equal(pickVoice([ko]), null, "영어 보이스가 없으면 null");
});

test("pickVoice: Android 식 언어 표기(en_US)와 대소문자 차이를 정규화한다", () => {
  const android = fakeVoice("en-us-x-tpf-local", "en_US", true);
  const lower = fakeVoice("x", "EN-gb");
  assert.equal(pickVoice([lower, android]), android);
  assert.equal(pickVoice([lower]), lower);
});

test("pickVoice: 'en' 으로 시작하지만 영어가 아닌 언어(예: eng 가 아닌 'enx')는 고르지 않는다", () => {
  assert.equal(pickVoice([fakeVoice("x", "enx-ZZ")]), null);
  assert.equal(pickVoice([fakeVoice("x", "en")]) !== null, true, "언어 코드만 'en' 인 보이스는 영어");
});

test("보이스가 이미 있으면 생성 시점에 고르고, utterance 에 보이스와 그 언어(하이픈 표기)를 넣는다", () => {
  const synth = new FakeSynth({ voices: [fakeVoice("Daniel", "en_GB", true)] });
  const speaker = createSpeaker({ synth, UtteranceCtor: HelperUtterance, warn: () => {} });
  assert.equal(speaker.getVoice().name, "Daniel");
  speaker.speak("apple");
  assert.equal(synth.lastUtterance.voice.name, "Daniel");
  assert.equal(synth.lastUtterance.lang, "en-GB", "en_GB 가 아니라 en-GB 로 넘긴다");
});

test("voiceschanged 지연 로딩: 처음엔 보이스가 없어도 재생되고, 이벤트 뒤에는 보이스를 쓴다", () => {
  const synth = new FakeSynth({ voices: [] });
  const speaker = createSpeaker({ synth, UtteranceCtor: HelperUtterance, warn: () => {} });
  assert.equal(speaker.getVoice(), null);
  assert.equal(speaker.speak("apple"), true, "보이스 준비를 기다리며 재생을 막지 않는다");
  assert.equal(synth.lastUtterance.voice, undefined, "보이스가 없으면 voice 를 건드리지 않고 lang 에 맡긴다");
  assert.equal(synth.lastUtterance.lang, "en-US");

  synth.setVoices([fakeVoice("Samantha", "en-US", true)]);
  assert.equal(speaker.getVoice(), null, "이벤트 전에는 아직 모른다");
  synth.emitVoicesChanged();
  assert.equal(speaker.getVoice().name, "Samantha");
  speaker.speak("banana");
  assert.equal(synth.lastUtterance.voice.name, "Samantha");
});

test("voiceschanged 가 오지 않는 브라우저(Safari 등)도 다음 재생 때 목록을 다시 읽는다", () => {
  const synth = new FakeSynth({ voices: [] });
  const speaker = createSpeaker({ synth, UtteranceCtor: HelperUtterance, warn: () => {} });
  synth.setVoices([fakeVoice("Samantha", "en-US", true)]); // 이벤트 없이 목록만 채워짐
  speaker.speak("apple");
  assert.equal(synth.lastUtterance.voice.name, "Samantha");
});

test("addEventListener 가 없으면 onvoiceschanged 속성으로 구독한다", () => {
  const synth = { cancel() {}, speak() {}, getVoices: () => [], onvoiceschanged: null };
  createSpeaker({ synth, UtteranceCtor: HelperUtterance, warn: () => {} });
  assert.equal(typeof synth.onvoiceschanged, "function");
});

test("getVoices 가 예외를 던져도 생성과 재생이 깨지지 않는다", () => {
  const synth = { cancel() {}, speak() {}, getVoices() { throw new Error("boom"); } };
  const speaker = createSpeaker({ synth, UtteranceCtor: HelperUtterance, warn: () => {} });
  assert.equal(speaker.getVoice(), null);
  assert.equal(speaker.speak("apple"), true);
});
