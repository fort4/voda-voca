/*
 * 2026-11-03 - voda-voca - 퀴즈 결과 문구: 전부 푼 결과와 일부만 푼 결과를 구분해 점수·정답률·안내를 만든다 (이슈 #8)
 * 파일 위치: src/frontend/js/core/quiz-result.js
 */

/**
 * @param {{total: number, answered: number, correct_count: number, accuracy: number}} summary
 * @returns {{score: string, accuracyLabel: string, note: string, perfect: boolean}}
 */
export function describeResult({ total, answered, correct_count: correct, accuracy }) {
  return {
    score: `${correct} / ${answered}`,
    accuracyLabel: answered > 0 ? `정답률 ${accuracy}%` : "푼 문항이 없습니다",
    note:
      answered < total
        ? `${total}문항 중 ${answered}문항을 풀었습니다. 정답률은 푼 문항 기준입니다.`
        : "",
    perfect: total > 0 && answered === total && correct === total,
  };
}

/**
 * 끝내지 못한 퀴즈의 안내. 이어 풀기는 지원하지 않으므로 새 퀴즈로 이어 가도록 알린다.
 * @param {{total: number, answered: number}} summary
 * @returns {string}
 */
export function retryGuidance({ total, answered }) {
  return answered < total ? "끝내지 못한 퀴즈는 이어 풀 수 없습니다. 새 퀴즈를 시작해 주세요." : "";
}
