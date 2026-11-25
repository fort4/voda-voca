/*
 * 2026-11-25 - voda-voca - 학습 분석 뷰모델: 자주 틀리는 단어 상위 N, 시험 성적 추이(회차별·날짜별 정답률) (DOM 없는 순수 로직, VOCA-FR-032, 033)
 * 파일 위치: src/frontend/js/core/analytics-model.js
 */

/**
 * @param {{items: Array<{word_id: number, vocabulary_title: string, term: string, meaning: string, wrong_count: number, answered_count: number}>}} data
 */
export function frequentWrongModel(data) {
  const peak = Math.max(1, ...data.items.map((i) => i.wrong_count));
  return {
    isEmpty: data.items.length === 0,
    items: data.items.map((i, index) => ({
      rank: index + 1,
      wordId: i.word_id,
      term: i.term,
      meaning: i.meaning,
      vocabularyTitle: i.vocabulary_title,
      countText: `${i.wrong_count}회 오답`,
      ratioText: `${i.answered_count}번 중 ${i.wrong_count}번 틀림`,
      ratio: Math.round((i.wrong_count / peak) * 100),
    })),
  };
}

/** 직전 회차와의 정답률 차이를 "+25%p" 꼴로. 첫 회차는 비교 대상이 없어 null. */
function changeText(previous, current) {
  if (previous === null) return null;
  const diff = Math.round((current - previous) * 10) / 10;
  if (diff === 0) return "변화 없음";
  return `${diff > 0 ? "+" : "-"}${Math.abs(diff)}%p`;
}

/**
 * @param {{sessions: Array<{round: number, session_id: number, correct: number, total: number, accuracy: number}>,
 *          daily: Array<{date: string, answered: number, correct: number, accuracy: number}>}} data
 */
export function scoreTrendModel(data) {
  const sessions = data.sessions.map((s, index) => ({
    label: `${s.round}회`,
    sessionId: s.session_id,
    scoreText: `${s.correct} / ${s.total}`,
    accuracyText: `${s.accuracy}%`,
    percent: Math.round(s.accuracy),
    change: changeText(index === 0 ? null : data.sessions[index - 1].accuracy, s.accuracy),
  }));
  const daily = data.daily.map((d) => ({
    label: d.date.slice(5).replace("-", "/"),
    percent: Math.round(d.accuracy),
    accuracyText: `${d.accuracy}%`,
    text: `${d.correct} / ${d.answered} 정답`,
  }));
  return { isEmpty: sessions.length === 0 && daily.length === 0, sessions, daily };
}
