/*
 * 2026-11-02 - voda-voca - 퀴즈 문항별 흐름 상태 머신 단위 테스트: 즉시 판정, 선택 잠금, 해설, 이동 규칙, 최종 제출 조건 (즉각 피드백)
 * 파일 위치: src/frontend/tests/quiz-flow.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createQuizFlow } from "../js/core/quiz-flow.js";

const SESSION = {
  session_id: 9,
  questions: [
    { question_id: 0, term: "apple", choices: ["사과", "배", "포도", "바나나"], correct_index: 0, example: "I eat an apple." },
    { question_id: 1, term: "pear", choices: ["자두", "배", "복숭아", "수박"], correct_index: 1, example: null },
    { question_id: 2, term: "kiwi", choices: ["키위", "레몬", "귤", "메론"], correct_index: 0, example: "Kiwi is sour." },
  ],
};

test("고른 보기는 즉시 정오가 판정되고 정답 뜻과 예문을 함께 준다", () => {
  const flow = createQuizFlow({ session: SESSION });
  const right = flow.choose(0);
  assert.equal(right.isCorrect, true);
  assert.equal(right.correctMeaning, "사과");
  assert.equal(right.example, "I eat an apple.");
  assert.equal(flow.index, 0, "판정해도 문항은 넘어가지 않는다");
});

test("틀린 보기는 오답으로 판정되고, 정답 선지 번호가 표시용으로 남는다", () => {
  const flow = createQuizFlow({ session: SESSION });
  const result = flow.choose(3);
  assert.equal(result.isCorrect, false);
  assert.equal(result.selectedIndex, 3);
  assert.equal(result.correctIndex, 0);
});

test("한 문항은 한 번 답하면 잠긴다. 다시 고르면 null 이고 판정은 바뀌지 않는다", () => {
  const flow = createQuizFlow({ session: SESSION });
  flow.choose(2);
  assert.equal(flow.choose(0), null);
  assert.equal(flow.feedbackFor(0).selectedIndex, 2);
  assert.equal(flow.feedbackFor(0).isCorrect, false);
});

test("선지 번호가 범위를 벗어나면 던진다", () => {
  const flow = createQuizFlow({ session: SESSION });
  assert.throws(() => flow.choose(4), /범위/);
  assert.throws(() => flow.choose(-1), /범위/);
  assert.throws(() => flow.choose(1.5), /범위/);
  assert.equal(flow.feedbackFor(0), null, "잘못된 입력은 기록되지 않는다");
});

test("다음 문항은 현재 문항에 답해야만 갈 수 있다", () => {
  const flow = createQuizFlow({ session: SESSION });
  assert.equal(flow.next(), false, "답하기 전에는 넘어갈 수 없다");
  flow.choose(0);
  assert.equal(flow.next(), true);
  assert.equal(flow.index, 1);
  assert.equal(flow.current().term, "pear");
});

test("마지막 문항에서는 next 가 false 이고 isLast 가 참이다", () => {
  const flow = createQuizFlow({ session: SESSION });
  flow.choose(0);
  flow.next();
  flow.choose(1);
  flow.next();
  flow.choose(0);
  assert.equal(flow.isLast(), true);
  assert.equal(flow.next(), false);
});

test("이전 문항으로 돌아가도 답은 그대로이고, 첫 문항에서는 멈춘다", () => {
  const flow = createQuizFlow({ session: SESSION });
  flow.choose(0);
  flow.next();
  assert.equal(flow.prev(), 0);
  assert.equal(flow.feedbackFor(0).isCorrect, true, "이전 문항의 판정은 유지된다");
  assert.equal(flow.prev(), 0, "첫 문항 밖으로 나가지 않는다");
});

test("해설 예문이 없으면 null 로 남는다", () => {
  const flow = createQuizFlow({ session: SESSION });
  flow.choose(0);
  flow.next();
  assert.equal(flow.choose(1).example, null);
});

test("최종 제출은 모든 문항에 답했을 때만 가능하고, 본문은 문항 번호 순이다", () => {
  const flow = createQuizFlow({ session: SESSION });
  assert.equal(flow.canFinish(), false);
  assert.throws(() => flow.toSubmitPayload(), /모든 문항/);
  flow.choose(0);
  flow.next();
  flow.choose(3);
  flow.next();
  flow.choose(0);
  assert.equal(flow.canFinish(), true);
  assert.deepEqual(flow.toSubmitPayload(), {
    answers: [
      { question_id: 0, choice_index: 0 },
      { question_id: 1, choice_index: 3 },
      { question_id: 2, choice_index: 0 },
    ],
  });
});

test("맞힌 개수와 진행률이 답에 따라 바뀐다", () => {
  const flow = createQuizFlow({ session: SESSION });
  assert.equal(flow.progressPercent(), 0);
  flow.choose(0); // 맞음
  flow.next();
  flow.choose(0); // 틀림
  assert.equal(flow.answeredCount(), 2);
  assert.equal(flow.correctCount(), 1);
  assert.equal(flow.progressPercent(), 67);
  assert.deepEqual([...flow.answerMap().entries()], [[0, 0], [1, 0], [2, null]]);
});

test("빈 세션은 제출할 수 없다", () => {
  const flow = createQuizFlow({ session: { questions: [] } });
  assert.equal(flow.canFinish(), false);
  assert.equal(flow.progressPercent(), 0);
});
