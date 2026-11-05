/*
 * 2026-11-05 - voda-voca - TTS 코어 확장 테스트: 단어/문장 프리셋, 재생 상태 구독(key 분리·연타 방어), 오류 분류, 세션당 1회 안내 (v2.2)
 * 파일 위치: src/frontend/tests/tts-state.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import * as tts from "../js/core/tts.js";
import { FakeSynth, FakeUtterance, fakeVoice } from "./helpers/fake-speech.js";

const { createSpeaker, SENTENCE_RATE, noticeMessage } = tts;

/** 경고·안내·상태 변화를 기록하는 스피커를 만든다. */
function setup({ voices = [fakeVoice("Samantha", "en-US", true)] } = {}) {
  const synth = new FakeSynth({ voices });
  const warnings = [];
  const notices = [];
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: (m, e) => warnings.push([m, e]), notify: (reason) => notices.push(reason) });
  const states = [];
  speaker.subscribe((state) => states.push({ ...state }));
  return { synth, speaker, warnings, notices, states };
}

const speaking = (key) => ({ status: "speaking", key });
const IDLE = { status: "idle", key: null };

// ---------- 프리셋 ----------

test("speakWord 는 속도 0.9, speakSentence 는 0.85 로 읽는다 (REQ-125: 단어 기준 0.9 유지)", () => {
  const { synth, speaker } = setup();
  assert.equal(SENTENCE_RATE, 0.85);
  assert.equal(speaker.speakWord("apple"), true);
  assert.equal(synth.lastUtterance.rate, 0.9);
  assert.equal(speaker.speakSentence("I ate an apple."), true);
  assert.equal(synth.lastUtterance.rate, 0.85);
  assert.equal(synth.lastUtterance.text, "I ate an apple.");
  assert.equal(synth.lastUtterance.pitch, 1.0);
});

test("프리셋도 빈 입력은 거부하고 상태를 바꾸지 않는다", () => {
  const { speaker, states, synth } = setup();
  assert.equal(speaker.speakWord(""), false);
  assert.equal(speaker.speakSentence("   "), false);
  assert.equal(speaker.speakWord(null), false);
  assert.deepEqual(states, []);
  assert.deepEqual(synth.log, []);
});

// ---------- 상태 구독 ----------

test("초기 상태는 idle 이고, 구독자에게 현재 상태를 바로 알려 주지는 않는다", () => {
  const { speaker, states } = setup();
  assert.deepEqual(speaker.getState(), IDLE);
  assert.deepEqual(states, []);
});

test("재생 요청 즉시 key 가 speaking 이 되고(옵티미스틱), onstart 는 중복 통지하지 않으며, 끝나면 idle", () => {
  const { synth, speaker, states } = setup();
  speaker.speakWord("apple", "word:1");
  assert.deepEqual(speaker.getState(), speaking("word:1"));
  synth.start();
  synth.finish();
  assert.deepEqual(states, [speaking("word:1"), IDLE], "상태가 바뀔 때만 한 번씩 통지한다");
});

test("연타해도 idle 로 깜박이지 않고 key 만 바뀐다 (cancel 이 보내는 interrupted 는 무시)", () => {
  const { synth, speaker, states, warnings } = setup();
  speaker.speakWord("apple", "word:1");
  synth.start();
  speaker.speakWord("banana", "word:2"); // 내부에서 cancel → 이전 발화에 interrupted
  speaker.speakWord("cherry", "word:3");
  assert.deepEqual(states, [speaking("word:1"), speaking("word:2"), speaking("word:3")], "중간에 idle 이 없다");
  assert.deepEqual(warnings, [], "interrupted 는 경고하지 않는다");
  synth.finish();
  assert.deepEqual(states.at(-1), IDLE);
});

test("같은 key 로 다시 눌러도(재시작) 통지는 늘지 않는다", () => {
  const { speaker, states } = setup();
  speaker.speakWord("apple", "word:1");
  speaker.speakWord("apple", "word:1");
  assert.deepEqual(states, [speaking("word:1")]);
});

test("이미 대체된 이전 발화의 늦은 이벤트(end/error)는 현재 상태를 바꾸지 않는다", () => {
  const { synth, speaker, states } = setup();
  speaker.speakWord("apple", "word:1");
  const first = synth.lastUtterance;
  speaker.speakWord("banana", "word:2");
  first.onend?.({});
  first.onerror?.({ error: "network" });
  assert.deepEqual(speaker.getState(), speaking("word:2"));
  assert.deepEqual(states.at(-1), speaking("word:2"));
});

test("stop 은 합성기를 취소하고 즉시 idle 로 만든다. 이미 idle 이면 통지하지 않는다", () => {
  const { synth, speaker, states } = setup();
  speaker.stop(); // idle 에서 호출
  assert.deepEqual(states, []);
  speaker.speakSentence("hello", "example:1");
  speaker.stop();
  assert.deepEqual(states, [speaking("example:1"), IDLE]);
  assert.equal(synth.calls.at(-1), "cancel", "마지막 호출이 cancel");
  assert.deepEqual(speaker.getState(), IDLE);
});

test("stop 뒤에 도착하는 interrupted 이벤트는 경고도 상태 변경도 만들지 않는다", () => {
  const { speaker, warnings, states } = setup();
  speaker.speakWord("apple", "word:1"); // FakeSynth.cancel 이 이전 발화에 interrupted 를 보낸다
  speaker.stop();
  assert.deepEqual(warnings, []);
  assert.deepEqual(states, [speaking("word:1"), IDLE]);
});

test("cancel 은 stop 의 별칭이다 (기존 호출처 호환)", () => {
  const { speaker, states } = setup();
  speaker.speakWord("apple", "word:1");
  speaker.cancel();
  assert.deepEqual(states.at(-1), IDLE);
});

test("구독 해제 후에는 통지받지 않고, 구독자 예외가 재생을 막지 않는다", () => {
  const { speaker } = setup();
  const seen = [];
  const off = speaker.subscribe((state) => seen.push(state.status));
  speaker.speakWord("a", "k1");
  off();
  speaker.speakWord("b", "k2");
  assert.deepEqual(seen, ["speaking"]);

  speaker.subscribe(() => { throw new Error("listener boom"); });
  assert.equal(speaker.speakWord("c", "k3"), true);
});

test("합성기가 speak 에서 예외를 던지면 speaking 에 갇히지 않고 idle 로 돌아간다", () => {
  const synth = new FakeSynth({ voices: [fakeVoice("Samantha", "en-US", true)] });
  synth.speak = () => { throw new Error("boom"); };
  const warnings = [];
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: (m) => warnings.push(m) });
  assert.equal(speaker.speakWord("apple", "word:1"), false);
  assert.deepEqual(speaker.getState(), IDLE);
  assert.equal(warnings.length, 1);
});

// ---------- 오류 분류와 세션당 1회 안내 ----------

test("interrupted / canceled 는 정상 종료: 경고 없이 idle", () => {
  for (const error of ["interrupted", "canceled"]) {
    const { synth, speaker, warnings, notices } = setup();
    speaker.speakWord("apple", "k");
    synth.fail(error);
    assert.deepEqual(speaker.getState(), IDLE, error);
    assert.deepEqual(warnings, [], error);
    assert.deepEqual(notices, [], error);
  }
});

test("not-allowed: 경고를 남기고 idle, 사용자 안내는 최초 1회만 (resetNotice 로 세션마다 다시)", () => {
  const { synth, speaker, warnings, notices } = setup();
  speaker.speakWord("apple", "k");
  synth.fail("not-allowed");
  assert.deepEqual(speaker.getState(), IDLE);
  assert.equal(warnings.length, 1);
  assert.deepEqual(notices, ["blocked"]);

  speaker.speakWord("apple", "k");
  synth.fail("not-allowed");
  assert.deepEqual(notices, ["blocked"], "두 번째부터는 안내하지 않는다");

  speaker.resetNotice(); // 새 학습 세션 시작
  speaker.speakWord("apple", "k");
  synth.fail("not-allowed");
  assert.deepEqual(notices, ["blocked", "blocked"]);
});

test("그 밖의 오류(synthesis-failed 등)는 경고만 하고 안내하지 않는다", () => {
  const { synth, speaker, warnings, notices } = setup();
  speaker.speakWord("apple", "k");
  synth.fail("synthesis-failed");
  assert.equal(warnings.length, 1);
  assert.deepEqual(notices, []);
  assert.deepEqual(speaker.getState(), IDLE);
});

test("영어 보이스가 하나도 없으면(목록은 채워졌는데 en 이 없음) 재생은 시도하되 안내는 1회", () => {
  const { synth, speaker, notices } = setup({ voices: [fakeVoice("Yuna", "ko-KR", true)] });
  assert.equal(speaker.speakWord("apple", "k"), true, "그래도 lang 으로 재생을 시도한다");
  assert.equal(synth.lastUtterance.lang, "en-US");
  speaker.speakWord("banana", "k");
  assert.deepEqual(notices, ["no-voice"]);
});

test("보이스 목록이 아직 비어 있으면(로딩 중) 영어 없음으로 오해해 안내하지 않는다", () => {
  const { speaker, notices } = setup({ voices: [] });
  speaker.speakWord("apple", "k");
  assert.deepEqual(notices, []);
});

test("음성 합성 미지원 브라우저: false, 안내 'unsupported' 1회, 상태는 idle", () => {
  const notices = [];
  const speaker = createSpeaker({ synth: undefined, UtteranceCtor: undefined, warn: () => {}, notify: (r) => notices.push(r) });
  assert.equal(speaker.speakWord("apple", "k"), false);
  assert.equal(speaker.speakSentence("hi", "k"), false);
  assert.deepEqual(notices, ["unsupported"]);
  assert.deepEqual(speaker.getState(), IDLE);
  assert.doesNotThrow(() => speaker.stop());
});

test("setNotifier 로 나중에 안내 함수를 연결할 수 있고, 안내 함수의 예외는 삼킨다", () => {
  const synth = new FakeSynth({ voices: [fakeVoice("Yuna", "ko-KR", true)] });
  const speaker = createSpeaker({ synth, UtteranceCtor: FakeUtterance, warn: () => {} });
  assert.doesNotThrow(() => speaker.speakWord("apple", "k"), "안내 함수가 없어도 안전");
  speaker.resetNotice();
  speaker.setNotifier(() => { throw new Error("toast boom"); });
  assert.doesNotThrow(() => speaker.speakWord("apple", "k"));
});

test("noticeMessage: 사유별 한글 문구, 모르는 사유도 문구를 돌려준다", () => {
  for (const reason of ["blocked", "no-voice", "unsupported", "???"]) {
    const message = noticeMessage(reason);
    assert.equal(typeof message, "string");
    assert.ok(message.length > 5 && /[가-힣]/.test(message), reason);
  }
  assert.notEqual(noticeMessage("blocked"), noticeMessage("no-voice"));
});

// ---------- 앱 전역 인스턴스용 export ----------

test("전역 편의 함수가 export 된다 (기존 speak 포함)", () => {
  for (const name of ["speak", "speakWord", "speakSentence", "stopSpeaking", "subscribeSpeaking", "getSpeakingState", "setSpeechNotifier", "resetSpeechNotice", "noticeMessage", "pickVoice"]) {
    assert.equal(typeof tts[name], "function", name);
  }
  assert.equal(typeof tts.speaker.getState, "function");
});
