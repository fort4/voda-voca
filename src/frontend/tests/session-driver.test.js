/*
 * 2026-11-05 - voda-voca - 세션 드라이버 테스트: 상태 머신의 효과를 API 호출로 실행하고 응답을 액션으로 되돌린다
 * 파일 위치: src/frontend/tests/session-driver.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { ACTION, PHASE } from "../js/core/session-runner.js";
import { createSessionDriver } from "../js/core/session-driver.js";

function session(total = 3) {
  return {
    session_id: 77,
    mode: "quiz",
    vocabulary_id: 1,
    vocabulary_title: "초급",
    total_questions: total,
    expires_at: "2026-11-05T09:30:00Z",
    composition: { wrong: 0, review: 0, unseen: total },
    items: Array.from({ length: total }, (_, i) => ({
      question_id: i,
      word_id: 100 + i,
      term: `t${i}`,
      context: null,
      options: ["a", "b", "c", "d"],
      meaning: null,
      example_meaning: null,
    })),
  };
}

function result(questionId, extra = {}) {
  return {
    question_id: questionId,
    is_correct: true,
    correct_index: 0,
    selected_index: 0,
    known: null,
    term: `t${questionId}`,
    meaning: "뜻",
    example: null,
    example_meaning: null,
    progress: { correct_count: 1, wrong_count: 0, consecutive_correct_count: 1, is_memorized: false },
    answered: questionId + 1,
    total: 3,
    is_finished: false,
    expires_at: "2026-11-05T09:30:00Z",
    ...extra,
  };
}

/** 호출을 기록하고, 테스트가 resolve/reject 시점을 정하는 가짜 api */
function fakeApi() {
  const calls = [];
  const api = (path, options) =>
    new Promise((resolve, reject) => {
      calls.push({ path, options, resolve, reject });
    });
  return { api, calls };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test("START: 세션 생성 API 를 부르고 응답이 오면 첫 문항이 활성화된다", async () => {
  const { api, calls } = fakeApi();
  const changes = [];
  const driver = createSessionDriver({ api, onChange: (state) => changes.push(state.phase) });

  driver.dispatch({ type: ACTION.START, mode: "quiz" });
  assert.equal(driver.getState().phase, PHASE.LOADING);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, "/study/sessions");
  assert.deepEqual(calls[0].options, { method: "POST", body: { mode: "quiz", count: 15, include_memorized: false } });

  calls[0].resolve(session());
  await tick();
  assert.equal(driver.getState().phase, PHASE.QUESTION_ACTIVE);
  assert.deepEqual(changes, [PHASE.LOADING, PHASE.QUESTION_ACTIVE]);
});

test("세션 생성 실패: ERROR 상태가 된다", async () => {
  const { api, calls } = fakeApi();
  const driver = createSessionDriver({ api });
  driver.dispatch({ type: ACTION.START });
  calls[0].reject({ status: 409, code: "NO_WORDS_TO_STUDY", detail: "학습할 단어가 없습니다." });
  await tick();
  assert.equal(driver.getState().phase, PHASE.ERROR);
  assert.equal(driver.getState().error.kind, "no_words");
});

async function activeDriver(api, calls) {
  const driver = createSessionDriver({ api });
  driver.dispatch({ type: ACTION.START });
  calls[0].resolve(session());
  await tick();
  return driver;
}

test("SUBMIT_ANSWER: 답 기록 API 를 부르고 응답이 오면 해설 상태가 된다", async () => {
  const { api, calls } = fakeApi();
  const driver = await activeDriver(api, calls);

  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 2 });
  assert.equal(calls[1].path, "/study/sessions/77/answer");
  assert.deepEqual(calls[1].options, { method: "POST", body: { question_id: 0, choice_index: 2 } });

  calls[1].resolve(result(0));
  await tick();
  assert.equal(driver.getState().phase, PHASE.FEEDBACK_SHOWING);
});

test("응답을 기다리는 동안의 중복 탭은 API 를 한 번만 부른다", async () => {
  const { api, calls } = fakeApi();
  const driver = await activeDriver(api, calls);
  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 });
  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 3 });
  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 });
  assert.equal(calls.length, 2, "세션 생성 1회 + 답 기록 1회");
});

test("네트워크 실패 후 RETRY: 같은 본문을 다시 보내고, 성공하면 해설 상태가 된다", async () => {
  const { api, calls } = fakeApi();
  const driver = await activeDriver(api, calls);
  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 });
  calls[1].reject({ status: 0, detail: "연결 실패" });
  await tick();
  assert.equal(driver.getState().error.kind, "network");

  driver.dispatch({ type: ACTION.RETRY });
  assert.equal(calls.length, 3);
  assert.deepEqual(calls[2].options.body, calls[1].options.body);
  calls[2].resolve(result(0));
  await tick();
  assert.equal(driver.getState().phase, PHASE.FEEDBACK_SHOWING);
  assert.equal(driver.getState().answered, 1);
});

test("만료 응답: EXPIRED 상태가 된다", async () => {
  const { api, calls } = fakeApi();
  const driver = await activeDriver(api, calls);
  driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  calls[1].reject({ status: 400, code: "QUIZ_EXPIRED", detail: "만료" });
  await tick();
  assert.equal(driver.getState().phase, PHASE.EXPIRED);
});

test("중단한 뒤 늦게 도착한 세션 생성 응답은 무시한다", async () => {
  const { api, calls } = fakeApi();
  const driver = createSessionDriver({ api });
  driver.dispatch({ type: ACTION.START });
  driver.dispatch({ type: ACTION.ABORT });
  calls[0].resolve(session());
  await tick();
  assert.equal(driver.getState().phase, PHASE.IDLE);
});

test("dispose 뒤에는 응답이 와도 상태와 화면 콜백을 건드리지 않는다", async () => {
  const { api, calls } = fakeApi();
  let changes = 0;
  const driver = createSessionDriver({ api, onChange: () => { changes += 1; } });
  driver.dispatch({ type: ACTION.START });
  const before = changes;
  driver.dispose();
  calls[0].resolve(session());
  await tick();
  assert.equal(changes, before);
  assert.equal(driver.getState().phase, PHASE.LOADING);
  assert.equal(driver.dispatch({ type: ACTION.ABORT }).phase, PHASE.LOADING, "dispose 뒤 dispatch 는 무시");
});

test("무시되는 액션은 onChange 를 부르지 않는다", () => {
  const { api } = fakeApi();
  let changes = 0;
  const driver = createSessionDriver({ api, onChange: () => { changes += 1; } });
  driver.dispatch({ type: ACTION.NEXT });
  driver.dispatch({ type: ACTION.ABORT });
  assert.equal(changes, 0);
});

test("전체 흐름: 3문항을 풀고 완료 상태가 된다", async () => {
  const { api, calls } = fakeApi();
  const driver = await activeDriver(api, calls);
  for (let i = 0; i < 3; i += 1) {
    driver.dispatch({ type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
    calls[calls.length - 1].resolve(result(i, { is_finished: i === 2 }));
    await tick();
    driver.dispatch({ type: ACTION.NEXT });
  }
  assert.equal(driver.getState().phase, PHASE.SESSION_COMPLETE);
  assert.equal(driver.getState().correct, 3);
});
