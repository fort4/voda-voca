/*
 * 2026-11-05 - voda-voca - 세션 화면 뷰모델 테스트: 선지 상태, 피드백 문구, 키 매핑, 오류 안내, 완료 문구
 * 파일 위치: src/frontend/tests/session-view-model.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { ACTION, PHASE, initialState, reduce, summaryOf } from "../js/core/session-runner.js";
import { choiceStates, completeCopy, errorCopy, feedbackTone, flashcardFaces, sessionKeyAction } from "../js/core/session-view-model.js";

// --- 상태 만들기 ---

function session(mode = "quiz") {
  return {
    session_id: 5,
    mode,
    vocabulary_id: 1,
    vocabulary_title: "초급",
    total_questions: 3,
    expires_at: "2026-11-05T09:30:00Z",
    composition: { wrong: 0, review: 0, unseen: 3 },
    items: [0, 1, 2].map((i) => ({
      question_id: i,
      word_id: 10 + i,
      term: `t${i}`,
      context: null,
      options: mode === "quiz" ? ["a", "b", "c", "d"] : null,
      meaning: mode === "flashcard" ? "뜻" : null,
      example_meaning: null,
    })),
  };
}

function active(mode = "quiz") {
  let state = reduce(initialState(), { type: ACTION.START, mode }).state;
  state = reduce(state, { type: ACTION.SESSION_LOADED, requestId: state.requestId, session: session(mode) }).state;
  return state;
}

function result(overrides = {}) {
  return {
    question_id: 0,
    is_correct: true,
    correct_index: 2,
    selected_index: 2,
    known: null,
    term: "t0",
    meaning: "뜻",
    example: "I like t0.",
    example_meaning: "해석",
    progress: { correct_count: 1, wrong_count: 0, consecutive_correct_count: 1, is_memorized: false },
    answered: 1,
    total: 3,
    is_finished: false,
    expires_at: "2026-11-05T09:30:00Z",
    ...overrides,
  };
}

function withFeedback(state, resultOverrides) {
  let s = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  s = reduce(s, { type: ACTION.ANSWER_RECEIVED, result: result(resultOverrides) }).state;
  return s;
}

// --- choiceStates ---

test("choiceStates: 풀기 전에는 모두 idle 이다", () => {
  assert.deepEqual(choiceStates(active()), ["idle", "idle", "idle", "idle"]);
});

test("choiceStates: 응답을 기다리는 동안 고른 선지만 selected 다", () => {
  const waiting = reduce(active(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 1 }).state;
  assert.deepEqual(choiceStates(waiting), ["idle", "selected", "idle", "idle"]);
});

test("choiceStates: 정답이면 고른 선지가 correct, 나머지는 dim 이다", () => {
  const state = withFeedback(active(), { is_correct: true, correct_index: 2, selected_index: 2 });
  assert.deepEqual(choiceStates(state), ["dim", "dim", "correct", "dim"]);
});

test("choiceStates: 오답이면 정답은 correct, 내가 고른 것은 wrong, 나머지는 dim 이다", () => {
  const state = withFeedback(active(), { is_correct: false, correct_index: 2, selected_index: 0 });
  assert.deepEqual(choiceStates(state), ["wrong", "dim", "correct", "dim"]);
});

test("choiceStates: 문항이 없거나 플래시카드면 빈 목록이다", () => {
  assert.deepEqual(choiceStates(initialState()), []);
  assert.deepEqual(choiceStates(active("flashcard")), []);
});

// --- feedbackTone ---

test("feedbackTone: 정답", () => {
  const tone = feedbackTone(withFeedback(active(), {}));
  assert.equal(tone.tone, "correct");
  assert.equal(tone.title, "🎉 정답입니다!");
  assert.equal(tone.buttonLabel, "다음 문항");
  assert.equal(tone.badge, null);
  assert.equal(tone.streakText, null);
});

test("feedbackTone: 오답은 확인 버튼이다", () => {
  const tone = feedbackTone(withFeedback(active(), { is_correct: false, selected_index: 0 }));
  assert.deepEqual([tone.tone, tone.title, tone.buttonLabel], ["wrong", "😅 아쉬워요!", "확인"]);
});

test("feedbackTone: 마지막 문항이면 버튼이 결과 보기다", () => {
  let state = active();
  for (let i = 0; i < 3; i += 1) {
    state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
    state = reduce(state, { type: ACTION.ANSWER_RECEIVED, result: result({ question_id: i }) }).state;
    if (i < 2) state = reduce(state, { type: ACTION.NEXT }).state;
  }
  assert.equal(feedbackTone(state).buttonLabel, "결과 보기");
});

test("feedbackTone: 방금 숙련되면 배지를 보인다", () => {
  const state = withFeedback(active(), { progress: { correct_count: 3, wrong_count: 0, consecutive_correct_count: 3, is_memorized: true } });
  assert.equal(feedbackTone(state).badge, "숙련 단어가 됐어요");
});

test("feedbackTone: 세션에서 연속 정답이 2회 이상이면 문구를 보인다", () => {
  let state = withFeedback(active(), { question_id: 0 });
  state = reduce(state, { type: ACTION.NEXT }).state;
  state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  state = reduce(state, { type: ACTION.ANSWER_RECEIVED, result: result({ question_id: 1 }) }).state;
  assert.equal(feedbackTone(state).streakText, "2문제 연속 정답!");
});

test("feedbackTone: 해설을 보는 상태가 아니면 null", () => {
  assert.equal(feedbackTone(active()), null);
});

// --- sessionKeyAction ---

test("키: 퀴즈에서 1~4 는 선지 선택이다", () => {
  const state = active();
  for (const [key, index] of [["1", 0], ["2", 1], ["3", 2], ["4", 3]]) {
    assert.deepEqual(sessionKeyAction(key, state), { type: ACTION.SUBMIT_ANSWER, choiceIndex: index }, key);
  }
  assert.equal(sessionKeyAction("5", state), null);
  assert.equal(sessionKeyAction("a", state), null);
});

test("키: 해설을 보는 중 Enter/Space 는 다음 문항이다", () => {
  const state = withFeedback(active(), {});
  assert.deepEqual(sessionKeyAction("Enter", state), { type: ACTION.NEXT });
  assert.deepEqual(sessionKeyAction(" ", state), { type: ACTION.NEXT });
  assert.equal(sessionKeyAction("1", state), null, "해설 중에는 선지 키가 없다");
});

test("키: 응답을 기다리는 중에는 키가 없다", () => {
  const waiting = reduce(active(), { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
  assert.equal(sessionKeyAction("2", waiting), null);
});

test("키: 플래시카드는 Space 로 뒤집고, 뒤집은 뒤 방향키로 평가한다", () => {
  const state = active("flashcard");
  assert.deepEqual(sessionKeyAction(" ", state, { flipped: false }), { type: "FLIP" });
  assert.equal(sessionKeyAction("ArrowRight", state, { flipped: false }), null, "뒤집기 전에는 평가할 수 없다");
  assert.deepEqual(sessionKeyAction("ArrowRight", state, { flipped: true }), { type: ACTION.EVALUATE_FLASHCARD, known: true });
  assert.deepEqual(sessionKeyAction("ArrowLeft", state, { flipped: true }), { type: ACTION.EVALUATE_FLASHCARD, known: false });
});

test("키: Escape 는 중단 요청이다 (진행 중일 때만)", () => {
  assert.deepEqual(sessionKeyAction("Escape", active()), { type: "REQUEST_ABORT" });
  assert.equal(sessionKeyAction("Escape", initialState()), null);
});

// --- errorCopy ---

test("errorCopy: 모든 오류 종류에 제목과 행동이 있다", () => {
  const kinds = ["network", "server", "expired", "no_words", "no_vocabulary", "locked", "word_missing", "invalid", "unauthorized", "unknown"];
  for (const kind of kinds) {
    const copy = errorCopy(kind);
    assert.ok(copy.title && copy.iconName, kind);
    assert.ok(copy.actions.length >= 1, kind);
    for (const action of copy.actions) assert.ok(action.label && action.action?.type, kind);
  }
});

test("errorCopy: 재시도할 수 있는 오류는 RETRY 를 준다", () => {
  for (const kind of ["network", "server"]) assert.equal(errorCopy(kind).actions[0].action.type, ACTION.RETRY, kind);
});

test("errorCopy: 단어가 없으면 숙련 단어를 포함해 다시 시작하도록 안내한다", () => {
  const [primary] = errorCopy("no_words").actions;
  assert.deepEqual(primary.action, { type: ACTION.START, includeMemorized: true });
});

test("errorCopy: 복습 세션에서 단어가 없으면 숙련 단어 포함을 권하지 않고 홈·복습함으로 안내한다", () => {
  for (const source of ["bookmarks", "wrong"]) {
    const copy = errorCopy("no_words", { source });
    assert.ok(!copy.actions.some((a) => a.action.includeMemorized), source);
    assert.ok(!copy.text.includes("숙련"), source);
    assert.ok(copy.actions.length >= 1);
  }
  assert.equal(errorCopy("no_words", { source: "all" }).actions[0].action.includeMemorized, true);
});

test("errorCopy: 건너뛸 수 있는 오류는 SKIP_QUESTION 을 준다", () => {
  for (const kind of ["locked", "word_missing"]) assert.equal(errorCopy(kind).actions[0].action.type, ACTION.SKIP_QUESTION, kind);
});

test("errorCopy: 만료는 푼 문항이 저장되었다고 알린다", () => {
  assert.match(errorCopy("expired").text, /저장/);
});

test("errorCopy: 알 수 없는 종류도 안전한 기본 안내가 있다", () => {
  assert.equal(errorCopy("???").title, errorCopy("unknown").title);
});

// --- completeCopy ---

function summaryFor({ correct, wrong, aborted = false }) {
  let state = active();
  let i = 0;
  for (const ok of [...Array(correct).fill(true), ...Array(wrong).fill(false)]) {
    state = reduce(state, { type: ACTION.SUBMIT_ANSWER, choiceIndex: 0 }).state;
    state = reduce(state, { type: ACTION.ANSWER_RECEIVED, result: result({ question_id: i, is_correct: ok }) }).state;
    if (i < 2) state = reduce(state, { type: ACTION.NEXT }).state;
    i += 1;
  }
  if (aborted) state = reduce(state, { type: ACTION.ABORT }).state;
  return summaryOf(state);
}

test("completeCopy: 정답률 구간별 제목", () => {
  assert.equal(completeCopy(summaryFor({ correct: 3, wrong: 0 })).title, "완벽해요!");
  assert.equal(completeCopy(summaryFor({ correct: 2, wrong: 1 })).title, "잘했어요!");
  assert.equal(completeCopy(summaryFor({ correct: 1, wrong: 2 })).title, "다음엔 더 잘할 수 있어요");
});

test("completeCopy: 중단했으면 푼 만큼만 알려 준다", () => {
  const copy = completeCopy(summaryFor({ correct: 1, wrong: 0, aborted: true }));
  assert.equal(copy.title, "학습을 마쳤어요");
  assert.match(copy.subtitle, /1문항/);
});

test("completeCopy: 하나도 풀지 않았으면 그대로 알린다", () => {
  const copy = completeCopy({ ...summaryFor({ correct: 0, wrong: 0 }), aborted: true });
  assert.equal(copy.title, "푼 문항이 없어요");
});

test("completeCopy: 정답률과 숙련 단어 수를 요약 줄에 담는다", () => {
  const summary = { ...summaryFor({ correct: 2, wrong: 1 }), memorizedTerms: ["apple", "pear"] };
  const copy = completeCopy(summary);
  assert.equal(copy.stats[0].value, "66.7%");
  assert.ok(copy.stats.some((s) => s.label === "새로 숙련" && s.value === "2개"));
});

test("completeCopy: 틀린 문항이 있을 때만 복습 안내를 보인다", () => {
  assert.equal(completeCopy(summaryFor({ correct: 3, wrong: 0 })).showWrongList, false);
  assert.equal(completeCopy(summaryFor({ correct: 2, wrong: 1 })).showWrongList, true);
});

test("PHASE 상수 확인 (뷰모델이 쓰는 상태 이름)", () => {
  assert.equal(PHASE.FEEDBACK_SHOWING, "FEEDBACK_SHOWING");
});

test("플래시카드 앞면은 단어만, 뒷면은 뜻·예문·예문 뜻을 담는다", () => {
  const item = { term: "apple", context: "I ate an apple.", meaning: "사과", example_meaning: "나는 사과를 먹었다." };
  assert.deepEqual(flashcardFaces(item), {
    front: { term: "apple" },
    back: { meaning: "사과", example: "I ate an apple.", exampleMeaning: "나는 사과를 먹었다." },
  });
});

test("플래시카드 뒷면은 예문이 없으면 해당 값을 null 로 둔다", () => {
  const faces = flashcardFaces({ term: "apple", context: null, meaning: "사과", example_meaning: null });
  assert.equal(faces.back.example, null);
  assert.equal(faces.back.exampleMeaning, null);
});
