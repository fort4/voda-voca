/*
 * 2026-11-02 - voda-voca - 퀴즈 문항별 흐름 상태 머신: 선택 즉시 판정, 선택 잠금, 해설 기록, 이전·다음 이동, 최종 제출 본문 (즉각 피드백)
 * 파일 위치: src/frontend/js/core/quiz-flow.js
 */

/**
 * @typedef {{question_id: number, term: string, choices: string[], correct_index: number, example: string|null, example_meaning?: string|null}} QuizQuestion
 * @typedef {{questionId: number, term: string, selectedIndex: number, correctIndex: number, isCorrect: boolean, correctMeaning: string, example: string|null, exampleMeaning: string|null}} QuizFeedback
 */

/**
 * 현재 화면에 무엇을 보일지 결정한다. 미선택 상태에서는 해설 카드를 만들지 않는다 (null 을 DOM 에 넘기지 않기 위해).
 * @param {{feedback: QuizFeedback|null|undefined, expired: boolean}} state
 * @returns {{showExplanation: boolean, showHint: boolean}}
 */
export function stageSlots({ feedback, expired }) {
  const answered = feedback !== null && feedback !== undefined;
  return {
    showExplanation: answered && !expired,
    showHint: !answered && !expired,
  };
}

/**
 * @param {{session: {questions: QuizQuestion[]}}} opts
 */
export function createQuizFlow({ session }) {
  const questions = session.questions;
  const total = questions.length;
  /** @type {Map<number, QuizFeedback>} 답한 문항의 판정 결과 (문항 번호 -> 판정) */
  const feedback = new Map();
  let index = 0;

  return {
    total,
    get index() {
      return index;
    },
    /** @returns {QuizQuestion} */
    current() {
      return questions[index];
    },
    /**
     * 현재 문항에 답한다. 한 번 답하면 잠긴다 (바꿀 수 없다). 이미 답했으면 null 을 돌려준다.
     * @param {number} choiceIndex
     * @returns {QuizFeedback|null}
     */
    choose(choiceIndex) {
      const question = questions[index];
      if (feedback.has(question.question_id)) return null;
      if (!Number.isInteger(choiceIndex) || choiceIndex < 0 || choiceIndex >= question.choices.length) {
        throw new Error(`선지 번호가 범위를 벗어났습니다: ${choiceIndex}`);
      }
      const result = {
        questionId: question.question_id,
        term: question.term,
        selectedIndex: choiceIndex,
        correctIndex: question.correct_index,
        isCorrect: choiceIndex === question.correct_index,
        correctMeaning: question.choices[question.correct_index],
        example: question.example ?? null,
        exampleMeaning: question.example_meaning ?? null,
      };
      feedback.set(question.question_id, result);
      return result;
    },
    /** @param {number} questionId @returns {QuizFeedback|null} */
    feedbackFor(questionId) {
      return feedback.get(questionId) ?? null;
    },
    isLast() {
      return index === total - 1;
    },
    /** 이전 문항으로. 답은 그대로 남는다. */
    prev() {
      if (index > 0) index -= 1;
      return index;
    },
    /** 다음 문항으로. 현재 문항에 답하지 않았거나 마지막이면 false. */
    next() {
      if (!feedback.has(questions[index].question_id)) return false;
      if (index >= total - 1) return false;
      index += 1;
      return true;
    },
    answeredCount() {
      return feedback.size;
    },
    correctCount() {
      let correct = 0;
      for (const item of feedback.values()) if (item.isCorrect) correct += 1;
      return correct;
    },
    /** 모든 문항에 답했는지. 최종 제출 조건이다. */
    canFinish() {
      return total > 0 && feedback.size === total;
    },
    progressPercent() {
      return total ? Math.round((feedback.size / total) * 100) : 0;
    },
    /** 제출 본문. 문항 번호 순으로 정렬한다. 모두 답하지 않았으면 만들지 않는다. */
    toSubmitPayload() {
      if (!this.canFinish()) throw new Error("모든 문항에 답해야 제출할 수 있습니다.");
      return {
        answers: questions
          .map((q) => ({ question_id: q.question_id, choice_index: feedback.get(q.question_id).selectedIndex }))
          .sort((a, b) => a.question_id - b.question_id),
      };
    },
    /** @returns {Map<number, number>} 문항 번호 -> 고른 선지 (결과 도출에 쓴다) */
    answerMap() {
      return new Map(questions.map((q) => [q.question_id, feedback.get(q.question_id)?.selectedIndex ?? null]));
    },
  };
}
