/*
 * 2026-11-02 - voda-voca - 퀴즈 답안 로컬 집계: 선택 저장, 진행률, 제출 본문, 제출 후 문항별 결과 도출 (정답 인덱스는 제출 후에만 사용) (REQ-014, REQ-015)
 * 파일 위치: src/frontend/js/core/quiz-state.js
 */

/**
 * @param {{questions: Array<{question_id: number, term: string, choices: string[]}>}} session
 */
export function createQuizState({ questions }) {
  /** @type {Map<number, number>} question_id -> choice_index */
  const answers = new Map();
  const ids = questions.map((q) => q.question_id);

  return {
    total: questions.length,
    /** @param {number} questionId @param {number} choiceIndex */
    select(questionId, choiceIndex) {
      if (!ids.includes(questionId)) throw new Error(`없는 문항입니다: ${questionId}`);
      if (!Number.isInteger(choiceIndex) || choiceIndex < 0 || choiceIndex > 3) {
        throw new Error(`선지 번호는 0~3 이어야 합니다: ${choiceIndex}`);
      }
      answers.set(questionId, choiceIndex);
    },
    /** @param {number} questionId @returns {number|null} */
    answerOf(questionId) {
      return answers.has(questionId) ? answers.get(questionId) : null;
    },
    answeredCount() {
      return answers.size;
    },
    unansweredCount() {
      return ids.length - answers.size;
    },
    allAnswered() {
      return ids.length > 0 && answers.size === ids.length;
    },
    /** 서버 제출 본문. 문항 번호 순서로 정렬한다. 모든 문항에 답해야 만든다. */
    toSubmitPayload() {
      if (!this.allAnswered()) throw new Error("모든 문항에 답해야 제출할 수 있습니다.");
      return {
        answers: ids
          .slice()
          .sort((a, b) => a - b)
          .map((id) => ({ question_id: id, choice_index: answers.get(id) })),
      };
    },
    /** 진행률 0~100 (답한 문항 비율). */
    progressPercent() {
      return ids.length ? Math.round((answers.size / ids.length) * 100) : 0;
    },
  };
}

/**
 * 제출 응답(wrong_items)과 로컬 답안으로 문항별 결과를 만든다.
 * 틀린 문항은 wrong_items 와 (단어 표제어, 고른 뜻)이 같은 문항을 찾아 정답 뜻의 선지 번호를 구한다.
 * 그 밖의 문항은 맞힌 것으로 보고 고른 선지가 정답이다.
 * @param {Array<{question_id: number, term: string, choices: string[]}>} questions
 * @param {Map<number, number>} answers
 * @param {Array<{word_id: number, term: string, correct_meaning: string, selected_meaning: string}>} wrongItems
 * @returns {Array<{question_id: number, term: string, choices: string[], selected_index: number, correct_index: number, is_correct: boolean, word_id: number|null}>}
 */
export function deriveQuizItems(questions, answers, wrongItems) {
  const pending = wrongItems.slice();
  return questions.map((q) => {
    const selected = answers.get(q.question_id);
    const matchIndex = pending.findIndex(
      (w) => w.term === q.term && q.choices[selected] === w.selected_meaning,
    );
    if (matchIndex >= 0) {
      const [wrong] = pending.splice(matchIndex, 1);
      return {
        question_id: q.question_id,
        term: q.term,
        choices: q.choices,
        selected_index: selected,
        correct_index: q.choices.indexOf(wrong.correct_meaning),
        is_correct: false,
        word_id: wrong.word_id,
      };
    }
    return {
      question_id: q.question_id,
      term: q.term,
      choices: q.choices,
      selected_index: selected,
      correct_index: selected,
      is_correct: true,
      word_id: null,
    };
  });
}
