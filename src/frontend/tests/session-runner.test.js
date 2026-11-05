/*
 * 2026-11-05 - voda-voca - 학습 세션 상태 머신 테스트: 전이, 퀴즈/플래시카드 모드, 연속 정답·숙련, 멱등 재시도, 만료, 중단, 요약
 * 파일 위치: src/frontend/tests/session-runner.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ACTION,
  EFFECT,
  PHASE,
  TRANSITIONS,
  classifyApiError,
  currentItem,
  initialState,
  progressOf,
  reduce,
  summaryOf,
} from "../js/core/session-runner.js";

// ---------------------------------------------------------------------------
// 도우미
// ---------------------------------------------------------------------------

const TOTAL = 15;

function makeSession({ mode = "quiz", total = TOTAL } = {}) {
  const items = Array.from({ length: total }, (_, i) => ({
    question_id: i,
    word_id: 100 + i,
    term: `t${i}`,
    context: `I like t${i}.`,
    options: mode === "quiz" ? [`a${i}`, `b${i}`, `c${i}`, `d${i}`] : null,
    meaning: mode === "flashcard" ? `뜻${i}` : null,
    example_meaning: mode === "flashcard" ? `해석${i}` : null,
  }));
  return {
    session_id: 77,
    mode,
    vocabulary_id: 2,
    vocabulary_title: "초급 필수 영단어 200",
    total_questions: total,
    expires_at: "2026-11-05T09:30:00Z",
    composition: { wrong: 4, review: 1, unseen: 10 },
    items,
  };
}

function makeResult(questionId, { correct = true, streak = 1, memorized = false, finished = false, mode = "quiz" } = {}) {
  return {
    question_id: questionId,
    is_correct: correct,
    correct_index: mode === "quiz" ? 0 : null,
    selected_index: mode === "quiz" ? (correct ? 0 : 1) : null,
    known: mode === "flashcard" ? correct : null,
    term: `t${questionId}`,
    meaning: `뜻${questionId}`,
    example: `I like t${questionId}.`,
    example_meaning: `해석${questionId}`,
    progress: {
      correct_count: streak,
      wrong_count: correct ? 0 : 1,
      consecutive_correct_count: correct ? streak : 0,
      is_memorized: memorized,
    },
    answered: questionId + 1,
    total: TOTAL,
    is_finished: finished,
    expires_at: "2026-11-05T09:30:00Z",
  };
}

/** 액션을 순서대로 적용하고 마지막 상태와 모든 효과를 돌려준다. */
function run(actions, state = initialState()) {
  const effects = [];
  for (const action of actions) {
    const out = reduce(state, action);
    state = out.state;
    effects.push(...out.effects);
  }
  return { state, effects };
}

function started(mode = "quiz", total = TOTAL) {
  const { state } = run([{ type: ACTION.START, mode }]);
  return run([{ type: ACTION.SESSION_LOADED, requestId: state.requestId, session: makeSession({ mode, total }) }], state).state;
}

/** 현재 문항에 답하고 서버 응답까지 받은 상태. */
function answered(state, resultOptions = {}) {
  const item = currentItem(state);
  const mode = state.mode;
  const submit = mode === "quiz" ? { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 } : { type: ACTION.EVALUATE_FLASHCARD, known: true };
  return run(
    [submit, { type: ACTION.ANSWER_RECEIVED, result: makeResult(item.question_id, { mode, ...resultOptions }) }],
    state,
  ).state;
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    Object.freeze(value);
    for (const key of Object.keys(value)) deepFreeze(value[key]);
  }
  return value;
}

// ---------------------------------------------------------------------------
// 시작과 로딩
// ---------------------------------------------------------------------------

test("초기 상태는 IDLE 이다", () => {
  const state = initialState();
  assert.equal(state.phase, PHASE.IDLE);
  assert.equal(currentItem(state), null);
});

test("START: LOADING 으로 가고 세션 생성 효과를 낸다 (기본 15문항, 숙련 단어 제외)", () => {
  const { state, effects } = reduce(initialState(), { type: ACTION.START });
  assert.equal(state.phase, PHASE.LOADING);
  assert.deepEqual(effects, [
    { type: EFFECT.CREATE_SESSION, requestId: state.requestId, body: { mode: "quiz", count: 15, include_memorized: false, source: "all" } },
  ]);
});

test("START: 모드, 문항 수, 숙련 단어 포함 옵션을 요청 본문에 싣는다", () => {
  const { effects } = reduce(initialState(), { type: ACTION.START, mode: "flashcard", count: 5, includeMemorized: true });
  assert.deepEqual(effects[0].body, { mode: "flashcard", count: 5, include_memorized: true, source: "all" });
});

test("START: 북마크·오답 복습은 source 를 서버로 보내고 상태에 기억한다", () => {
  for (const source of ["bookmarks", "wrong"]) {
    const { state, effects } = reduce(initialState(), { type: ACTION.START, source });
    assert.equal(effects[0].body.source, source);
    assert.equal(state.source, source);
  }
});

test("START: 알 수 없는 source 는 all 로 본다", () => {
  const { state, effects } = reduce(initialState(), { type: ACTION.START, source: "everything" });
  assert.equal(effects[0].body.source, "all");
  assert.equal(state.source, "all");
});

test("START: source 없이 다시 시작하면 직전 세션의 source 를 이어 간다 (복습 다시 시작)", () => {
  const ended = { ...initialState(), phase: PHASE.SESSION_COMPLETE, source: "wrong", mode: "flashcard" };
  const { state, effects } = reduce(ended, { type: ACTION.START });
  assert.equal(effects[0].body.source, "wrong");
  assert.equal(state.source, "wrong");
});

test("START: 이미 진행 중이면 무시한다 (중복 시작 방지)", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  assert.deepEqual(reduce(loading, { type: ACTION.START }), { state: loading, effects: [] });
  const active = started();
  assert.deepEqual(reduce(active, { type: ACTION.START }), { state: active, effects: [] });
});

test("SESSION_LOADED: 첫 문항이 활성화되고 진행 정보가 만들어진다", () => {
  const state = started();
  assert.equal(state.phase, PHASE.QUESTION_ACTIVE);
  assert.equal(state.sessionId, 77);
  assert.equal(state.vocabularyTitle, "초급 필수 영단어 200");
  assert.equal(state.items.length, TOTAL);
  assert.equal(currentItem(state).question_id, 0);
  assert.deepEqual(progressOf(state), { current: 1, total: 15, ratio: 1 / 15 });
});

test("SESSION_LOADED: 서버가 알려 준 모드를 따른다", () => {
  assert.equal(started("flashcard").mode, "flashcard");
});

test("SESSION_LOADED: 요청 번호가 다르면 늦게 온 응답으로 보고 무시한다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const out = reduce(loading, { type: ACTION.SESSION_LOADED, requestId: loading.requestId + 5, session: makeSession() });
  assert.equal(out.state.phase, PHASE.LOADING);
});

test("SESSION_LOADED: 문항이 비어 있으면 바로 완료다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const out = reduce(loading, { type: ACTION.SESSION_LOADED, requestId: loading.requestId, session: makeSession({ total: 0 }) });
  assert.equal(out.state.phase, PHASE.SESSION_COMPLETE);
});

test("SESSION_LOAD_FAILED: ERROR 로 가고 원인 종류와 문구를 담는다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const error = { status: 409, code: "NO_WORDS_TO_STUDY", detail: "학습할 단어가 없습니다." };
  const { state } = reduce(loading, { type: ACTION.SESSION_LOAD_FAILED, requestId: loading.requestId, error });
  assert.equal(state.phase, PHASE.ERROR);
  assert.equal(state.error.kind, "no_words");
  assert.equal(state.error.message, "학습할 단어가 없습니다.");
});

test("ERROR 에서 숙련 단어를 포함해 다시 시작할 수 있다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const failed = reduce(loading, {
    type: ACTION.SESSION_LOAD_FAILED,
    requestId: loading.requestId,
    error: { status: 409, code: "NO_WORDS_TO_STUDY", detail: "x" },
  }).state;
  const out = reduce(failed, { type: ACTION.START, includeMemorized: true });
  assert.equal(out.state.phase, PHASE.LOADING);
  assert.equal(out.effects[0].body.include_memorized, true);
});

// ---------------------------------------------------------------------------
// 퀴즈 모드
// ---------------------------------------------------------------------------

test("SUBMIT_ANSWER: 답을 대기 상태로 두고 서버 전송 효과를 낸다", () => {
  const { state, effects } = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 2 });
  assert.equal(state.phase, PHASE.QUESTION_ACTIVE);
  assert.deepEqual(state.pending, { questionId: 0, body: { question_id: 0, choice_index: 2 } });
  assert.deepEqual(effects, [
    { type: EFFECT.SEND_ANSWER, sessionId: 77, body: { question_id: 0, choice_index: 2 } },
  ]);
});

test("SUBMIT_ANSWER: 응답을 기다리는 중의 두 번째 탭은 무시한다 (더블 탭 방지)", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 2 }).state;
  assert.deepEqual(reduce(waiting, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 3 }), { state: waiting, effects: [] });
});

test("SUBMIT_ANSWER: 범위 밖 선지는 무시한다", () => {
  const state = started();
  for (const choiceIndex of [-1, 4, 1.5, "1", undefined]) {
    assert.deepEqual(reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex }), { state, effects: [] }, String(choiceIndex));
  }
});

test("퀴즈 세션에서 플래시카드 액션은 무시한다", () => {
  const state = started("quiz");
  assert.deepEqual(reduce(state, { type: ACTION.EVALUATE_FLASHCARD, known: true }), { state, effects: [] });
});

test("ANSWER_RECEIVED(정답): FEEDBACK_SHOWING 으로 가고 해설과 집계가 반영된다", () => {
  const state = answered(started(), { streak: 1 });
  assert.equal(state.phase, PHASE.FEEDBACK_SHOWING);
  assert.equal(state.pending, null);
  assert.equal(state.feedback.is_correct, true);
  assert.equal(state.feedback.meaning, "뜻0");
  assert.equal(state.feedback.word_id, 100);
  assert.equal(state.feedback.justMemorized, false);
  assert.deepEqual([state.answered, state.correct, state.wrong, state.streak, state.bestStreak], [1, 1, 0, 1, 1]);
});

test("ANSWER_RECEIVED(오답): 세션 연속 정답은 끊기지만 최고 기록은 남는다", () => {
  let state = started();
  state = reduce(answered(state), { type: ACTION.NEXT }).state;
  state = reduce(answered(state), { type: ACTION.NEXT }).state;
  assert.equal(state.streak, 2);
  state = answered(state, { correct: false });
  assert.deepEqual([state.correct, state.wrong, state.streak, state.bestStreak], [2, 1, 0, 2]);
});

test("숙련 전이: 연속 정답 3회째에만 '방금 숙련'이다 (4회째는 아니다)", () => {
  const third = answered(started(), { streak: 3, memorized: true });
  assert.equal(third.feedback.justMemorized, true);
  assert.deepEqual(third.memorizedTerms, ["t0"]);

  const fourth = answered(started(), { streak: 4, memorized: true });
  assert.equal(fourth.feedback.justMemorized, false);
  assert.deepEqual(fourth.memorizedTerms, []);
});

test("숙련 전이: 오답이면 숙련이 아니다", () => {
  const state = answered(started(), { correct: false });
  assert.equal(state.feedback.justMemorized, false);
  assert.equal(state.feedback.progress.is_memorized, false);
});

test("ANSWER_RECEIVED: 대기 중인 문항과 다른 응답, 중복 응답은 무시한다", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  const wrongQuestion = reduce(waiting, { type: ACTION.ANSWER_RECEIVED, result: makeResult(5) });
  assert.equal(wrongQuestion.state.phase, PHASE.QUESTION_ACTIVE);

  const done = reduce(waiting, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) }).state;
  const duplicate = reduce(done, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) });
  assert.deepEqual(duplicate, { state: done, effects: [] });
  assert.equal(done.answered, 1, "한 번만 센다");
});

test("ANSWER_RECEIVED: 답하지 않았는데 온 응답은 무시한다", () => {
  const state = started();
  assert.deepEqual(reduce(state, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) }), { state, effects: [] });
});

test("NEXT: 다음 문항으로 가고 해설과 대기 상태를 비운다", () => {
  const { state } = reduce(answered(started()), { type: ACTION.NEXT });
  assert.equal(state.phase, PHASE.QUESTION_ACTIVE);
  assert.equal(currentItem(state).question_id, 1);
  assert.equal(state.feedback, null);
  assert.equal(state.pending, null);
  assert.deepEqual(progressOf(state), { current: 2, total: 15, ratio: 2 / 15 });
});

test("NEXT: 해설을 보는 중이 아니면 무시한다", () => {
  const state = started();
  assert.deepEqual(reduce(state, { type: ACTION.NEXT }), { state, effects: [] });
});

test("NEXT: 마지막 문항 뒤에는 SESSION_COMPLETE 다", () => {
  let state = started("quiz", 3);
  for (let i = 0; i < 3; i += 1) state = reduce(answered(state), { type: ACTION.NEXT }).state;
  assert.equal(state.phase, PHASE.SESSION_COMPLETE);
  assert.equal(state.aborted, false);
});

test("NEXT: 서버가 세션이 끝났다고 하면 남은 문항이 있어도 완료다", () => {
  const state = answered(started(), { finished: true });
  assert.equal(reduce(state, { type: ACTION.NEXT }).state.phase, PHASE.SESSION_COMPLETE);
});

test("15문항 전체를 끝까지 푼다", () => {
  let state = started();
  for (let i = 0; i < TOTAL; i += 1) {
    assert.equal(currentItem(state).question_id, i);
    state = reduce(answered(state, { correct: i % 5 !== 4 }), { type: ACTION.NEXT }).state;
  }
  assert.equal(state.phase, PHASE.SESSION_COMPLETE);
  assert.deepEqual(summaryOf(state), {
    total: 15,
    answered: 15,
    correct: 12,
    wrong: 3,
    skipped: 0,
    unanswered: 0,
    accuracy: 80,
    bestStreak: 4,
    memorizedTerms: [],
    wrongItems: [4, 9, 14].map((i) => ({ word_id: 100 + i, term: `t${i}`, meaning: `뜻${i}` })),
    aborted: false,
  });
});

// ---------------------------------------------------------------------------
// 플래시카드 모드
// ---------------------------------------------------------------------------

test("EVALUATE_FLASHCARD: 알아요/헷갈려요를 known 으로 보낸다", () => {
  const { state, effects } = reduce(started("flashcard"), { type: ACTION.EVALUATE_FLASHCARD, known: false });
  assert.deepEqual(state.pending.body, { question_id: 0, known: false });
  assert.deepEqual(effects, [{ type: EFFECT.SEND_ANSWER, sessionId: 77, body: { question_id: 0, known: false } }]);
});

test("EVALUATE_FLASHCARD: known 이 boolean 이 아니면 무시하고, 중복 평가도 무시한다", () => {
  const state = started("flashcard");
  assert.deepEqual(reduce(state, { type: ACTION.EVALUATE_FLASHCARD, known: "yes" }), { state, effects: [] });
  const waiting = reduce(state, { type: ACTION.EVALUATE_FLASHCARD, known: true }).state;
  assert.deepEqual(reduce(waiting, { type: ACTION.EVALUATE_FLASHCARD, known: false }), { state: waiting, effects: [] });
});

test("플래시카드 세션에서 퀴즈 답 액션은 무시한다", () => {
  const state = started("flashcard");
  assert.deepEqual(reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }), { state, effects: [] });
});

test("플래시카드: 알아요는 정답처럼 집계되고 연속 정답이 이어진다", () => {
  let state = started("flashcard");
  state = reduce(answered(state), { type: ACTION.NEXT }).state;
  state = answered(state);
  assert.deepEqual([state.correct, state.wrong, state.streak], [2, 0, 2]);
  assert.equal(state.feedback.known, true);
});

// ---------------------------------------------------------------------------
// 멱등 재시도와 오류 전이
// ---------------------------------------------------------------------------

test("네트워크 오류: 문항은 그대로 두고 재시도 가능 오류로 표시한다", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 }).state;
  const { state } = reduce(waiting, { type: ACTION.ANSWER_FAILED, error: { status: 0, detail: "연결 실패" } });
  assert.equal(state.phase, PHASE.QUESTION_ACTIVE);
  assert.equal(state.error.kind, "network");
  assert.equal(state.error.retryable, true);
  assert.deepEqual(state.pending, waiting.pending, "고른 답은 유지된다");
});

test("RETRY: 같은 본문으로 다시 보낸다 (서버가 멱등으로 처리한다)", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 }).state;
  const failed = reduce(waiting, { type: ACTION.ANSWER_FAILED, error: { status: 503, detail: "x" } }).state;
  assert.equal(failed.error.kind, "server");

  const { state, effects } = reduce(failed, { type: ACTION.RETRY });
  assert.equal(state.error, null);
  assert.deepEqual(effects, [{ type: EFFECT.SEND_ANSWER, sessionId: 77, body: { question_id: 0, choice_index: 1 } }]);

  const recovered = reduce(state, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) }).state;
  assert.equal(recovered.phase, PHASE.FEEDBACK_SHOWING);
  assert.equal(recovered.answered, 1);
});

test("RETRY: 재시도할 오류가 없으면 무시한다", () => {
  const state = started();
  assert.deepEqual(reduce(state, { type: ACTION.RETRY }), { state, effects: [] });
});

test("오류가 난 문항에서는 다른 답으로 바꿀 수 없다 (기록된 답은 잠긴다)", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 }).state;
  const failed = reduce(waiting, { type: ACTION.ANSWER_FAILED, error: { status: 0, detail: "x" } }).state;
  assert.deepEqual(reduce(failed, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 2 }), { state: failed, effects: [] });
});

test("만료: EXPIRED 로 가고 지금까지의 집계는 남는다", () => {
  let state = reduce(answered(started()), { type: ACTION.NEXT }).state;
  state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  const out = reduce(state, { type: ACTION.ANSWER_FAILED, error: { status: 400, code: "QUIZ_EXPIRED", detail: "x" } }).state;
  assert.equal(out.phase, PHASE.EXPIRED);
  assert.equal(out.pending, null);
  assert.equal(summaryOf(out).answered, 1, "푼 문항은 이미 저장되어 있다");
  assert.equal(reduce(out, { type: ACTION.START }).state.phase, PHASE.LOADING, "새 세션을 시작할 수 있다");
});

test("이미 끝난 세션(다른 탭 등): SESSION_COMPLETE 로 간다", () => {
  const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  const out = reduce(waiting, { type: ACTION.ANSWER_FAILED, error: { status: 409, code: "QUIZ_ALREADY_SUBMITTED", detail: "x" } }).state;
  assert.equal(out.phase, PHASE.SESSION_COMPLETE);
});

test("잠긴 답 / 삭제된 단어: 이 문항을 건너뛸 수 있는 오류로 표시한다", () => {
  for (const code of ["QUIZ_ANSWER_LOCKED", "QUIZ_WORD_MISSING"]) {
    const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
    const { state } = reduce(waiting, { type: ACTION.ANSWER_FAILED, error: { status: 409, code, detail: "x" } });
    assert.equal(state.phase, PHASE.QUESTION_ACTIVE, code);
    assert.equal(state.error.skippable, true, code);
    assert.equal(state.pending, null, code);
  }
});

test("SKIP_QUESTION: 다음 문항으로 가고 건너뜀과 연속 정답 끊김을 반영한다", () => {
  let state = reduce(answered(started()), { type: ACTION.NEXT }).state;
  state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  state = reduce(state, { type: ACTION.ANSWER_FAILED, error: { status: 409, code: "QUIZ_WORD_MISSING", detail: "x" } }).state;
  const { state: next } = reduce(state, { type: ACTION.SKIP_QUESTION });
  assert.equal(currentItem(next).question_id, 2);
  assert.equal(next.error, null);
  assert.deepEqual([next.skipped, next.streak], [1, 0]);
});

test("SKIP_QUESTION: 건너뛸 수 없는 상황이면 무시하고, 마지막 문항이면 완료다", () => {
  const plain = started();
  assert.deepEqual(reduce(plain, { type: ACTION.SKIP_QUESTION }), { state: plain, effects: [] });

  let state = started("quiz", 1);
  state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  state = reduce(state, { type: ACTION.ANSWER_FAILED, error: { status: 409, code: "QUIZ_WORD_MISSING", detail: "x" } }).state;
  assert.equal(reduce(state, { type: ACTION.SKIP_QUESTION }).state.phase, PHASE.SESSION_COMPLETE);
});

test("검증 실패(400)·인증 실패(401)·알 수 없는 오류: ERROR 로 간다", () => {
  for (const error of [
    { status: 400, code: "QUIZ_ANSWER_INVALID", detail: "x" },
    { status: 401, detail: "x" },
    { status: 404, detail: "x" },
  ]) {
    const waiting = reduce(started(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
    assert.equal(reduce(waiting, { type: ACTION.ANSWER_FAILED, error }).state.phase, PHASE.ERROR, String(error.status));
  }
});

test("classifyApiError: 상태와 오류 코드를 화면이 다루는 종류로 바꾼다", () => {
  const cases = [
    [{ status: 0 }, "network"],
    [{ status: 500 }, "server"],
    [{ status: 503 }, "server"],
    [{ status: 429 }, "server"],
    [{ status: 401 }, "unauthorized"],
    [{ status: 400, code: "QUIZ_EXPIRED" }, "expired"],
    [{ status: 409, code: "QUIZ_ALREADY_SUBMITTED" }, "already_submitted"],
    [{ status: 409, code: "QUIZ_ANSWER_LOCKED" }, "locked"],
    [{ status: 409, code: "QUIZ_WORD_MISSING" }, "word_missing"],
    [{ status: 400, code: "QUIZ_ANSWER_INVALID" }, "invalid"],
    [{ status: 409, code: "NO_WORDS_TO_STUDY" }, "no_words"],
    [{ status: 409, code: "NO_VOCABULARY" }, "no_vocabulary"],
    [{ status: 404 }, "unknown"],
    [null, "unknown"],
  ];
  for (const [error, kind] of cases) assert.equal(classifyApiError(error), kind, JSON.stringify(error));
});

// ---------------------------------------------------------------------------
// 중단과 초기화
// ---------------------------------------------------------------------------

test("ABORT: 풀던 세션을 완료로 닫고 푼 만큼을 요약에 남긴다", () => {
  let state = reduce(answered(started()), { type: ACTION.NEXT }).state;
  state = answered(state, { correct: false });
  const out = reduce(state, { type: ACTION.ABORT }).state;
  assert.equal(out.phase, PHASE.SESSION_COMPLETE);
  const summary = summaryOf(out);
  assert.equal(summary.aborted, true);
  assert.deepEqual([summary.answered, summary.correct, summary.wrong, summary.unanswered], [2, 1, 1, 13]);
  assert.equal(summary.accuracy, 50);
});

test("ABORT: 로딩 중이면 IDLE 로 돌아가고, 늦게 온 세션은 무시한다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const aborted = reduce(loading, { type: ACTION.ABORT }).state;
  assert.equal(aborted.phase, PHASE.IDLE);
  const late = reduce(aborted, { type: ACTION.SESSION_LOADED, requestId: loading.requestId, session: makeSession() });
  assert.equal(late.state.phase, PHASE.IDLE);
});

test("ABORT: 시작 전(IDLE)이나 이미 끝난 뒤에는 아무 일도 없다", () => {
  const idle = initialState();
  assert.deepEqual(reduce(idle, { type: ACTION.ABORT }), { state: idle, effects: [] });
});

test("RESET: IDLE 로 돌아가고 진행 중이던 요청의 응답은 무시된다", () => {
  const loading = reduce(initialState(), { type: ACTION.START }).state;
  const reset = reduce(loading, { type: ACTION.RESET }).state;
  assert.equal(reset.phase, PHASE.IDLE);
  assert.equal(reduce(reset, { type: ACTION.SESSION_LOADED, requestId: loading.requestId, session: makeSession() }).state.phase, PHASE.IDLE);
});

test("SESSION_COMPLETE 에서 새로 시작하면 집계가 초기화된다", () => {
  let state = started("quiz", 1);
  state = reduce(answered(state), { type: ACTION.NEXT }).state;
  assert.equal(state.phase, PHASE.SESSION_COMPLETE);
  const restarted = reduce(state, { type: ACTION.START }).state;
  assert.deepEqual([restarted.phase, restarted.answered, restarted.correct, restarted.items.length], [PHASE.LOADING, 0, 0, 0]);
});

// ---------------------------------------------------------------------------
// 요약·진행 정보
// ---------------------------------------------------------------------------

test("summaryOf: 푼 문항이 없으면 정답률은 0 이다", () => {
  assert.equal(summaryOf(started()).accuracy, 0);
});

test("summaryOf: 정답률은 소수 첫째 자리까지 반올림한다", () => {
  let state = started();
  for (const correct of [true, false, false]) state = reduce(answered(state, { correct }), { type: ACTION.NEXT }).state;
  assert.equal(summaryOf(state).accuracy, 33.3);
});

test("progressOf: 문항이 없으면 0/0", () => {
  assert.deepEqual(progressOf(initialState()), { current: 0, total: 0, ratio: 0 });
});

// ---------------------------------------------------------------------------
// 순수성과 전이 다이어그램
// ---------------------------------------------------------------------------

test("reduce 는 입력 상태를 바꾸지 않는다", () => {
  let state = deepFreeze(started());
  for (const action of [
    { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 },
    { type: ACTION.ANSWER_FAILED, error: { status: 0 } },
    { type: ACTION.RETRY },
  ]) {
    state = deepFreeze(reduce(state, action).state);
  }
  state = deepFreeze(reduce(state, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) }).state);
  deepFreeze(reduce(state, { type: ACTION.NEXT }).state);
});

test("알 수 없는 액션은 상태를 그대로 둔다", () => {
  const state = started();
  assert.deepEqual(reduce(state, { type: "NOPE" }), { state, effects: [] });
  assert.deepEqual(reduce(state, null), { state, effects: [] });
});

test("전이 다이어그램: 어떤 시나리오에서도 문서화된 전이만 일어난다", () => {
  const seen = new Set();
  const track = (state, action) => {
    const out = reduce(state, action);
    if (out.state.phase !== state.phase) seen.add(`${state.phase}->${out.state.phase}`);
    return out.state;
  };
  const expired = (s) => track(track(s, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }), { type: ACTION.ANSWER_FAILED, error: { status: 400, code: "QUIZ_EXPIRED" } });

  // IDLE -> LOADING -> QUESTION_ACTIVE -> FEEDBACK_SHOWING -> QUESTION_ACTIVE ... -> SESSION_COMPLETE
  let s = track(initialState(), { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOADED, requestId: s.requestId, session: makeSession({ total: 2 }) });
  for (let i = 0; i < 2; i += 1) {
    s = track(s, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
    s = track(s, { type: ACTION.ANSWER_RECEIVED, result: makeResult(i) });
    s = track(s, { type: ACTION.NEXT });
  }
  // SESSION_COMPLETE -> LOADING, 로딩 실패 -> ERROR -> LOADING, 중단, 만료
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOAD_FAILED, requestId: s.requestId, error: { status: 0 } });
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.ABORT }); // LOADING -> IDLE
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOADED, requestId: s.requestId, session: makeSession() });
  s = track(s, { type: ACTION.ABORT }); // QUESTION_ACTIVE -> SESSION_COMPLETE
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOADED, requestId: s.requestId, session: makeSession() });
  s = expired(s); // QUESTION_ACTIVE -> EXPIRED
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.RESET }); // LOADING -> IDLE
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOADED, requestId: s.requestId, session: makeSession() });
  s = track(s, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  s = track(s, { type: ACTION.ANSWER_FAILED, error: { status: 400, code: "QUIZ_ANSWER_INVALID" } }); // -> ERROR
  s = track(s, { type: ACTION.START });
  s = track(s, { type: ACTION.SESSION_LOADED, requestId: s.requestId, session: makeSession() });
  s = track(s, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 });
  s = track(s, { type: ACTION.ANSWER_RECEIVED, result: makeResult(0) });
  s = track(s, { type: ACTION.ABORT }); // FEEDBACK_SHOWING -> SESSION_COMPLETE

  const allowed = new Set(Object.entries(TRANSITIONS).flatMap(([from, targets]) => targets.map((to) => `${from}->${to}`)));
  for (const pair of seen) assert.ok(allowed.has(pair), `문서에 없는 전이: ${pair}`);
  for (const pair of [
    "IDLE->LOADING",
    "LOADING->QUESTION_ACTIVE",
    "LOADING->ERROR",
    "LOADING->IDLE",
    "QUESTION_ACTIVE->FEEDBACK_SHOWING",
    "FEEDBACK_SHOWING->QUESTION_ACTIVE",
    "FEEDBACK_SHOWING->SESSION_COMPLETE",
    "QUESTION_ACTIVE->SESSION_COMPLETE",
    "QUESTION_ACTIVE->EXPIRED",
    "QUESTION_ACTIVE->ERROR",
    "SESSION_COMPLETE->LOADING",
    "ERROR->LOADING",
    "EXPIRED->LOADING",
  ]) {
    assert.ok(seen.has(pair), `시나리오가 다루지 못한 전이: ${pair}`);
  }
});

test("TRANSITIONS 의 모든 상태는 PHASE 에 있다", () => {
  const phases = new Set(Object.values(PHASE));
  for (const [from, targets] of Object.entries(TRANSITIONS)) {
    assert.ok(phases.has(from), from);
    for (const to of targets) assert.ok(phases.has(to), to);
  }
});
