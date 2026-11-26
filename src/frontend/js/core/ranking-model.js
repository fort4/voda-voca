/*
 * 2026-11-26 - voda-voca - 학습 순위 뷰모델: 지표 이름과 값 표시, 본인 요약, 공개 설정 저장 (DOM 없는 순수 로직, REQ-172, REQ-173)
 * 파일 위치: src/frontend/js/core/ranking-model.js
 */

const VISIBILITY_PATH = "/users/me/ranking-visibility";

/** 서버의 metric 값과 화면 표시. 순서가 곧 선택 칸 순서이며 첫 항목이 기본이다. */
export const RANKING_METRICS = Object.freeze([
  { id: "learned_words", label: "학습 단어", unit: "개", description: "한 번 이상 맞힌 서로 다른 단어 수예요 (누적)." },
  { id: "week_words", label: "7일 단어", unit: "개", description: "오늘을 포함한 최근 7일에 푼 서로 다른 단어 수예요." },
  { id: "week_days", label: "7일 학습일", unit: "일", description: "오늘을 포함한 최근 7일 중 학습한 날 수예요." },
]);

export const RANKING_VISIBILITY_NOTE = "닉네임과 학습 지표가 다른 사용자에게 보여요. 단어장과 단어는 보이지 않아요.";

/** @returns {string} 예: "학습 단어 30개" */
const metricText = (metric, values) => `${metric.label} ${values[metric.id]}${metric.unit}`;

/**
 * @param {{metric: string, total_public: number,
 *          items: Array<{rank: number, nickname: string, is_me: boolean, learned_words: number, week_words: number, week_days: number}>,
 *          me: {public: boolean, rank: number|null, learned_words: number, week_words: number, week_days: number}}} response
 */
export function rankingModel(response) {
  const chosen = RANKING_METRICS.find((m) => m.id === response.metric) ?? RANKING_METRICS[0];
  const others = RANKING_METRICS.filter((m) => m !== chosen);
  const { me } = response;
  return {
    metric: chosen.id,
    description: chosen.description,
    totalText: `공개 ${response.total_public}명`,
    limitText: response.total_public > response.items.length ? `상위 ${response.items.length}명만 보여요` : null,
    isEmpty: response.items.length === 0,
    rows: response.items.map((item) => ({
      rank: item.rank,
      nickname: item.nickname,
      isMe: item.is_me,
      valueText: `${item[chosen.id]}${chosen.unit}`,
      otherText: others.map((m) => metricText(m, item)).join(" · "),
    })),
    me: {
      isPublic: me.public,
      title: me.public ? `내 순위 ${me.rank}위` : "비공개 상태예요",
      detail: RANKING_METRICS.map((m) => metricText(m, me)).join(" · "),
      hint: me.public ? null : "내 기록은 순위표에 나오지 않고, 위 지표는 나만 볼 수 있어요.",
    },
  };
}

/**
 * 순위 공개 스위치의 상태. 먼저 바꾸고 저장하며, 실패하면 이전 값으로 되돌린다. 저장 중의 추가 입력은 무시한다.
 * value 가 null 이면 아직 서버 값을 모르는 상태라, 누르면 저장하지 않고 다시 읽는다.
 * @param {{api: (path: string, options?: object) => Promise<any>,
 *          onChange: (state: {value: boolean|null, busy: boolean, failed: boolean}) => void}} deps
 */
export function createRankingVisibility({ api, onChange }) {
  /** @type {boolean|null} */
  let value = null;
  let busy = false;
  let failed = false;
  const emit = () => onChange({ value, busy, failed });

  async function load() {
    if (busy) return;
    busy = true;
    failed = false;
    emit();
    try {
      value = (await api(VISIBILITY_PATH)).public;
    } catch {
      failed = true;
    }
    busy = false;
    emit();
  }

  /** @returns {Promise<boolean>} 저장에 실패했을 때만 false */
  async function toggle() {
    if (busy) return true;
    if (value === null) {
      await load();
      return true;
    }
    const previous = value;
    value = !previous;
    busy = true;
    emit();
    try {
      value = (await api(VISIBILITY_PATH, { method: "PUT", body: { public: value } })).public;
      return true;
    } catch {
      value = previous;
      return false;
    } finally {
      busy = false;
      emit();
    }
  }

  return { load, toggle };
}
