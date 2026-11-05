/*
 * 2026-11-05 - voda-voca - 통계 화면 뷰모델: 서버 집계(/study/stats)와 카탈로그를 합쳐 누적 지표, 주간 활동, 단어장별 진행률을 만든다 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/stats-page-model.js
 */

const KO = "ko-KR";
const NO_DATA = "—";

/**
 * @param {{answered: number, accuracy: number|null, streak_days: number, total_words: number, wrong_word_count: number,
 *          weekly: Array<{date: string, label: string, count: number, is_today: boolean}>,
 *          vocabulary_progress: Array<{vocabulary_id: number, word_count: number, learned_words: number, percent: number}>}} stats
 * @param {Array<{id: number, title: string, user_progress: {is_active: boolean}}>|null} catalog 못 받았으면 null (제목은 대체 문구)
 */
export function statsPageModel(stats, catalog) {
  const byId = new Map((catalog ?? []).map((v) => [v.id, v]));
  const peak = Math.max(0, ...stats.weekly.map((day) => day.count));
  const weekly = stats.weekly.map((day) => ({
    date: day.date,
    label: day.label,
    count: day.count,
    isToday: day.is_today,
    ratio: peak === 0 ? 0 : day.count / peak,
  }));
  const vocabularies = stats.vocabulary_progress.map((p) => ({
    id: p.vocabulary_id,
    title: byId.get(p.vocabulary_id)?.title ?? `단어장 ${p.vocabulary_id}`,
    percent: p.percent,
    isActive: byId.get(p.vocabulary_id)?.user_progress.is_active === true,
    text: `${p.learned_words.toLocaleString(KO)} / ${p.word_count.toLocaleString(KO)} 학습`,
  }));
  return {
    isEmpty: stats.answered === 0,
    accuracy:
      stats.accuracy === null
        ? { value: NO_DATA, hint: "기록 없음" }
        : { value: `${Math.round(stats.accuracy)}%`, hint: `누적 ${stats.answered.toLocaleString(KO)}문항` },
    streak: stats.streak_days > 0 ? { value: `${stats.streak_days}일`, hint: "오늘 기준" } : null,
    totalWords: stats.total_words.toLocaleString(KO),
    wrongWordCount: stats.wrong_word_count,
    weekly,
    weekTotal: weekly.reduce((sum, day) => sum + day.count, 0),
    vocabularies,
    vocabulariesActiveFirst: [...vocabularies.filter((v) => v.isActive), ...vocabularies.filter((v) => !v.isActive)],
  };
}
