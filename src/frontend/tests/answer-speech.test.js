/*
 * 2026-11-26 - voda-voca - 퀴즈 채점 직후 정답 영단어 자동 발음 검사: 대상, 효과음 뒤 재생, 음소거, 취소, iOS 재생 허용 준비
 * 파일 위치: src/frontend/tests/answer-speech.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createAnswerSpeech, cueDurationMs } from "../js/core/answer-speech.js";
import { ACTION } from "../js/core/session-runner.js";
import { createSpeaker } from "../js/core/tts.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");

function setup({ muted = false, hidden = false } = {}) {
  const spoken = [];
  const timers = new Map();
  let seq = 0;
  const flags = { muted, hidden };
  const speech = createAnswerSpeech({
    speak: (text, key) => spoken.push([text, key]),
    prime: () => spoken.push("prime"),
    muted: () => flags.muted,
    hidden: () => flags.hidden,
    schedule: (fn, ms) => { timers.set(++seq, { fn, ms }); return seq; },
    unschedule: (id) => timers.delete(id),
  });
  const run = () => { for (const [id, t] of [...timers]) { timers.delete(id); t.fn(); } };
  const delays = () => [...timers.values()].map((t) => t.ms);
  return { speech, spoken, flags, run, delays };
}

const answered = (isCorrect, mode = "quiz") => [
  { mode, feedback: { term: "apple", is_correct: isCorrect } },
  { type: ACTION.ANSWER_RECEIVED },
];

for (const isCorrect of [true, false]) {
  test(`퀴즈 ${isCorrect ? "정답" : "오답"} 채점이 오면 영단어를 읽는다 (헤더 발음 버튼과 같은 key)`, () => {
    const { speech, spoken, run } = setup();
    speech.play(...answered(isCorrect), null);
    run();
    assert.deepEqual(spoken, [["apple", "word:apple"]]);
  });
}

test("효과음이 났으면 그 길이만큼 기다린 뒤 읽고, 없으면 바로 읽는다", () => {
  assert.equal(cueDurationMs("correct"), 320);
  assert.equal(cueDurationMs("wrong"), 250);
  assert.equal(cueDurationMs("milestone"), 640);
  assert.equal(cueDurationMs(null), 0);
  const withCue = setup();
  withCue.speech.play(...answered(true), "correct");
  assert.ok(withCue.delays()[0] >= 320);
  assert.deepEqual(withCue.spoken, [], "효과음과 겹치지 않는다");
  const noCue = setup();
  noCue.speech.play(...answered(true), null);
  assert.deepEqual(noCue.delays(), [0]);
});

test("플래시카드, 채점 응답이 아닌 액션, 영단어가 없는 응답은 읽지 않는다", () => {
  const { speech, delays } = setup();
  speech.play(...answered(true, "flashcard"), null);
  speech.play(answered(true)[0], { type: ACTION.NEXT }, null);
  speech.play({ mode: "quiz", feedback: null }, { type: ACTION.ANSWER_RECEIVED }, null);
  assert.deepEqual(delays(), []);
});

test("효과음을 끄면 자동 발음도 나지 않는다 (예약 뒤에 꺼도)", () => {
  const off = setup({ muted: true });
  off.speech.play(...answered(true), null);
  off.speech.unlock();
  off.run();
  assert.deepEqual(off.spoken, []);
  const later = setup();
  later.speech.play(...answered(true), "correct");
  later.flags.muted = true;
  later.run();
  assert.deepEqual(later.spoken, []);
});

test("cancel 하면 예약한 발음이 나지 않고, 탭이 숨겨진 상태에서도 읽지 않는다", () => {
  const { speech, spoken, run } = setup();
  speech.play(...answered(true), "correct");
  speech.cancel();
  run();
  assert.deepEqual(spoken, []);
  const hidden = setup({ hidden: true });
  hidden.speech.play(...answered(false), null);
  hidden.run();
  assert.deepEqual(hidden.spoken, []);
});

test("prime: 첫 호출만 소리 없는 발화를 보내고 재생 상태를 바꾸지 않는다 (iOS 는 제스처 안의 첫 발화가 필요하다)", () => {
  const sent = [];
  const speaker = createSpeaker({
    synth: { getVoices: () => [], speak: (u) => sent.push(u), cancel: () => {} },
    UtteranceCtor: class { constructor(text) { this.text = text; } },
  });
  assert.equal(speaker.prime(), true);
  assert.equal(speaker.prime(), false);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].volume, 0);
  assert.equal(speaker.getState().status, "idle");
});

test("prime: 미지원 환경에서는 조용히 false", () => {
  assert.equal(createSpeaker({ synth: null, UtteranceCtor: null }).prime(), false);
});

test("세션 화면 배선: 답할 때 준비, 채점 응답에 재생, 다음·중단·문항 전환·화면 정리에 취소", () => {
  const view = read("js/views/study-session-view.js");
  assert.match(view, /createAnswerSpeech\(\)/);
  assert.match(view, /case ACTION\.SUBMIT_ANSWER:\s*answerSpeech\.unlock\(\)/);
  assert.match(view, /answerSpeech\.play\(state, action, /);
  assert.equal(view.match(/answerSpeech\.cancel\(\);\s*stopSpeaking\(\)/g)?.length, 3, "문항 전환, 다음·중단, 화면 정리");
  assert.match(view, /return \(\) => \{[\s\S]*answerSpeech\.cancel\(\)[\s\S]*driver\.dispose/);
});
