/*
 * 2026-11-03 - voda-voca - 퀴즈 답 기록 큐 단위 테스트: 순서 보장, 재시도, 영구 실패 분리, 다시 시도, 비움 대기 (이슈 #8)
 * 파일 위치: src/frontend/tests/answer-recorder.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { ApiError } from "../js/core/api.js";
import { createAnswerRecorder } from "../js/core/answer-recorder.js";

const noSleep = async () => {};
const networkError = () => new ApiError({ status: 0, detail: "연결 실패" });
const lockedError = () => new ApiError({ status: 409, detail: "잠김", code: "QUIZ_ANSWER_LOCKED" });

/** 호출 기록을 남기고, 호출 번호별로 실패를 주입할 수 있는 가짜 send. */
function fakeSend(failures = {}) {
  const calls = [];
  const send = async ({ questionId, choiceIndex }) => {
    calls.push({ questionId, choiceIndex });
    const failure = failures[calls.length];
    if (failure) throw failure();
    return { question_id: questionId, expires_at: `T${calls.length}` };
  };
  return { send, calls };
}

test("답은 고른 순서대로 하나씩 보낸다", async () => {
  const { send, calls } = fakeSend();
  const recorder = createAnswerRecorder({ send, sleep: noSleep });
  recorder.enqueue(0, 2);
  recorder.enqueue(1, 0);
  recorder.enqueue(2, 3);
  await recorder.flush();
  assert.deepEqual(calls, [
    { questionId: 0, choiceIndex: 2 },
    { questionId: 1, choiceIndex: 0 },
    { questionId: 2, choiceIndex: 3 },
  ]);
  assert.equal(recorder.isIdle(), true);
  assert.deepEqual(recorder.failed, []);
});

test("기록될 때마다 onRecorded 로 서버 응답을 넘긴다 (마감 시각 갱신용)", async () => {
  const { send } = fakeSend();
  const seen = [];
  const recorder = createAnswerRecorder({ send, sleep: noSleep, onRecorded: (result) => seen.push(result.expires_at) });
  recorder.enqueue(0, 1);
  recorder.enqueue(1, 1);
  await recorder.flush();
  assert.deepEqual(seen, ["T1", "T2"]);
});

test("같은 문항을 두 번 넣어도 한 번만 보낸다", async () => {
  const { send, calls } = fakeSend();
  const recorder = createAnswerRecorder({ send, sleep: noSleep });
  recorder.enqueue(0, 1);
  recorder.enqueue(0, 1);
  await recorder.flush();
  assert.equal(calls.length, 1);
});

test("네트워크 오류는 간격을 두고 다시 시도하고, 성공하면 실패로 남기지 않는다", async () => {
  const { send, calls } = fakeSend({ 1: networkError, 2: networkError });
  const waited = [];
  const recorder = createAnswerRecorder({
    send,
    sleep: async (ms) => waited.push(ms),
    retryDelaysMs: [10, 20, 30],
  });
  recorder.enqueue(0, 1);
  await recorder.flush();
  assert.equal(calls.length, 3);
  assert.deepEqual(waited, [10, 20]);
  assert.deepEqual(recorder.failed, []);
});

test("서버 오류(5xx)와 요청 과다(429)도 다시 시도한다", async () => {
  const { send, calls } = fakeSend({
    1: () => new ApiError({ status: 503, detail: "점검 중" }),
    2: () => new ApiError({ status: 429, detail: "많음" }),
  });
  const recorder = createAnswerRecorder({ send, sleep: noSleep });
  recorder.enqueue(0, 1);
  await recorder.flush();
  assert.equal(calls.length, 3);
  assert.deepEqual(recorder.failed, []);
});

test("다시 시도해도 소용없는 오류(4xx)는 바로 실패로 분리하고 다음 답은 계속 보낸다", async () => {
  const { send, calls } = fakeSend({ 1: lockedError });
  const recorder = createAnswerRecorder({ send, sleep: noSleep });
  recorder.enqueue(0, 1);
  recorder.enqueue(1, 2);
  await recorder.flush();
  assert.equal(calls.length, 2, "재시도 없이 다음 문항으로 넘어간다");
  assert.equal(recorder.failed.length, 1);
  assert.equal(recorder.failed[0].questionId, 0);
  assert.equal(recorder.failed[0].error.code, "QUIZ_ANSWER_LOCKED");
});

test("재시도 횟수를 다 쓰면 실패로 분리하고, retryFailed 로 다시 보낼 수 있다", async () => {
  const { send, calls } = fakeSend({ 1: networkError, 2: networkError, 3: networkError });
  const recorder = createAnswerRecorder({ send, sleep: noSleep, retryDelaysMs: [1, 1] });
  recorder.enqueue(0, 1);
  await recorder.flush();
  assert.equal(calls.length, 3, "처음 1번 + 재시도 2번");
  assert.equal(recorder.failed.length, 1);

  recorder.retryFailed();
  await recorder.flush();
  assert.equal(calls.length, 4);
  assert.deepEqual(recorder.failed, []);
});

test("isIdle 은 전송 중에는 false 이고 flush 후에는 true 다", async () => {
  const { send } = fakeSend();
  const recorder = createAnswerRecorder({ send, sleep: noSleep });
  assert.equal(recorder.isIdle(), true);
  recorder.enqueue(0, 1);
  assert.equal(recorder.isIdle(), false);
  await recorder.flush();
  assert.equal(recorder.isIdle(), true);
});

test("onChange 는 대기·실패 개수가 바뀔 때 호출된다", async () => {
  const { send } = fakeSend({ 1: lockedError });
  const states = [];
  const recorder = createAnswerRecorder({ send, sleep: noSleep, onChange: (s) => states.push(`${s.pending}/${s.failed}`) });
  recorder.enqueue(0, 1);
  await recorder.flush();
  assert.equal(states.at(-1), "0/1");
  assert.ok(states.some((s) => s.startsWith("1/")), "대기 중 상태가 한 번은 알려져야 한다");
});

test("flush 는 보낼 것이 없으면 바로 끝난다", async () => {
  const recorder = createAnswerRecorder({ send: async () => ({}), sleep: noSleep });
  await recorder.flush();
  assert.equal(recorder.isIdle(), true);
});
