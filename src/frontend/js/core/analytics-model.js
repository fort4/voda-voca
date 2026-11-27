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

/** 접힌 상태에서 보이는 개수 */
const FREQUENT_COLLAPSED = 5;

/**
 * 자주 틀리는 단어의 접힘·펼침 상태에서 보일 내용. 5개 이하이면 펼칠 것이 없어 toggle 은 null 이다.
 * @param {ReturnType<typeof frequentWrongModel>} model
 * @param {boolean} expanded
 */
export function frequentWrongListModel(model, expanded) {
  const items = expanded ? model.items : model.items.slice(0, FREQUENT_COLLAPSED);
  const toggle = expanded ? { label: "접기", iconName: "chevron-up", expanded: true } : { label: "더 보기", iconName: "chevron-down", expanded: false };
  return {
    items,
    countText: `상위 ${items.length}개`,
    toggle: model.items.length > FREQUENT_COLLAPSED ? toggle : null,
  };
}

/** 직전 회차와의 정답률 차이를 "+25%p" 꼴로. 첫 회차는 비교 대상이 없어 null. */
function changeText(previous, current) {
  if (previous === null) return null;
  const diff = Math.round((current - previous) * 10) / 10;
  if (diff === 0) return "변화 없음";
  return `${diff > 0 ? "+" : "-"}${Math.abs(diff)}%p`;
}

/** 최근 회차의 정답률과 직전 회차 대비 방향(up·down·flat). 첫 회차는 비교 대상이 없다. */
function latestSummary(sessions) {
  const last = sessions.at(-1);
  if (!last) return null;
  const direction = last.change === null ? null : last.change.startsWith("+") ? "up" : last.change.startsWith("-") ? "down" : "flat";
  return { accuracyText: last.accuracyText, change: last.change, direction };
}

/** 기간 평균 정답률. 날마다 푼 문항 수가 다르므로 문항 수로 가중한다. */
function averageText(daily) {
  const answered = daily.reduce((sum, d) => sum + d.answered, 0);
  if (answered === 0) return null;
  const correct = daily.reduce((sum, d) => sum + d.correct, 0);
  return `${Math.round((correct / answered) * 100)}%`;
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
  return {
    isEmpty: sessions.length === 0 && daily.length === 0,
    sessions,
    daily,
    latestSession: latestSummary(sessions),
    dailyAverageText: averageText(data.daily),
  };
}
