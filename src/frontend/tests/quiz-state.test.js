/*
 * 2026-11-02 - voda-voca - 퀴즈 답안 로컬 집계 단위 테스트: 선택 검증, 진행률, 일괄 제출 본문, 제출 후 문항별 결과 도출 (REQ-014, REQ-015)
 * 파일 위치: src/frontend/tests/quiz-state.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createQuizState, deriveQuizItems } from "../js/core/quiz-state.js";

const QUESTIONS = [
  { question_id: 0, term: "apple", choices: ["사과", "배", "포도", "바나나"] },
  { question_id: 1, term: "pear", choices: ["자두", "배", "복숭아", "수박"] },
  { question_id: 2, term: "kiwi", choices: ["키위", "레몬", "귤", "메론"] },
];

test("select 는 문항과 선지 범위를 검사한다", () => {
  const quiz = createQuizState({ questions: QUESTIONS });
  assert.throws(() => quiz.select(9, 0), /없는 문항/);
  assert.throws(() => quiz.select(0, 4), /0~3/);
  assert.throws(() => quiz.select(0, 1.5), /0~3/);
  quiz.select(0, 2);
  assert.equal(quiz.answerOf(0), 2);
  quiz.select(0, 3);
  assert.equal(quiz.answerOf(0), 3, "다시 고르면 바뀐다");
  assert.equal(quiz.answerOf(1), null);
});

test("진행률과 미답 개수가 답한 만큼 바뀐다", () => {
  const quiz = createQuizState({ questions: QUESTIONS });
  assert.equal(quiz.progressPercent(), 0);
  quiz.select(0, 0);
  assert.equal(quiz.answeredCount(), 1);
  assert.equal(quiz.unansweredCount(), 2);
  assert.equal(quiz.progressPercent(), 33);
  quiz.select(1, 1);
  quiz.select(2, 0);
  assert.equal(quiz.allAnswered(), true);
  assert.equal(quiz.progressPercent(), 100);
});

test("제출 본문은 문항 번호 순으로 정렬하고, 다 답하지 않으면 만들지 않는다", () => {
  const quiz = createQuizState({ questions: QUESTIONS });
  quiz.select(2, 0);
  quiz.select(0, 3);
  assert.throws(() => quiz.toSubmitPayload(), /모든 문항/);
  quiz.select(1, 1);
  assert.deepEqual(quiz.toSubmitPayload(), {
    answers: [
      { question_id: 0, choice_index: 3 },
      { question_id: 1, choice_index: 1 },
      { question_id: 2, choice_index: 0 },
    ],
  });
});

test("deriveQuizItems: 틀린 문항은 오답 목록과 짝지어 정답 선지 번호를 찾는다", () => {
  const answers = new Map([[0, 0], [1, 2], [2, 0]]);
  const wrongItems = [
    { word_id: 11, term: "pear", correct_meaning: "배", selected_meaning: "복숭아" },
  ];
  const items = deriveQuizItems(QUESTIONS, answers, wrongItems);
  assert.equal(items[0].is_correct, true);
  assert.equal(items[0].correct_index, 0, "맞힌 문항은 고른 선지가 정답");
  assert.equal(items[1].is_correct, false);
  assert.equal(items[1].correct_index, 1, "정답 뜻 '배'의 선지 번호");
  assert.equal(items[1].selected_index, 2);
  assert.equal(items[1].word_id, 11);
  assert.equal(items[2].is_correct, true);
});

test("deriveQuizItems: 같은 표제어가 둘이어도 고른 뜻으로 올바른 문항을 짝짓는다", () => {
  const questions = [
    { question_id: 0, term: "run", choices: ["달리다", "걷다", "뛰다", "멈추다"] },
    { question_id: 1, term: "run", choices: ["달리다2", "걷다2", "뛰다2", "멈추다2"] },
  ];
  const answers = new Map([[0, 1], [1, 0]]);
  const wrongItems = [{ word_id: 5, term: "run", correct_meaning: "달리다", selected_meaning: "걷다" }];
  const items = deriveQuizItems(questions, answers, wrongItems);
  assert.equal(items[0].is_correct, false);
  assert.equal(items[0].correct_index, 0);
  assert.equal(items[1].is_correct, true, "두 번째 run 은 맞힌 문항이다");
});
