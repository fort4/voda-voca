/*
 * 2026-11-05 - voda-voca - 콤보(연속 정답) 순수 모델: 증가·리셋·최대 추적, 노출 기준, 마일스톤, 뱃지 바운스 판정, 사운드 큐 정책 (v2.2)
 * 파일 위치: src/frontend/js/core/combo-model.js
 */

/** 이 값 이상일 때 뱃지를 보인다 (2연속 정답부터). */
export const COMBO_MIN_VISIBLE = 2;

/** 마일스톤 콤보. 세션이 15문항이라 최대 세 번 닿는다. */
export const MILESTONES = Object.freeze([5, 10, 15]);

/** @param {unknown} value @returns {number} 0 이상의 정수가 아니면 0 */
const asCount = (value) => (Number.isInteger(value) && /** @type {number} */ (value) > 0 ? /** @type {number} */ (value) : 0);

/**
 * 답 하나를 반영한 다음 콤보. 입력을 바꾸지 않는다.
 * 정답이면 count 가 1 늘고, 그 밖(오답·건너뜀·알 수 없는 값)은 count 를 0 으로 끊는다. max 는 줄지 않는다.
 * @param {{count: number, max: number} | undefined} combo
 * @param {"correct" | "wrong" | "skip"} outcome
 * @returns {{count: number, max: number}}
 */
export function advanceCombo(combo, outcome) {
  const count = outcome === "correct" ? asCount(combo?.count) + 1 : 0;
  return { count, max: Math.max(asCount(combo?.max), count) };
}

/** @param {number} count @returns {boolean} 뱃지를 보여야 하는지 */
export const comboVisible = (count) => asCount(count) >= COMBO_MIN_VISIBLE;

/** @param {number} count @returns {boolean} 마일스톤(5·10·15)에 닿았는지 */
export const isMilestone = (count) => MILESTONES.includes(count);

/**
 * 뱃지를 어떻게 그릴지. 세션 화면은 상태가 바뀔 때마다 다시 그려지므로,
 * 바운스는 직전에 그린 값보다 **늘어난 렌더**에서만 켠다.
 * @param {number} prevCount 직전에 그린 콤보
 * @param {number} count 지금 콤보
 * @returns {{visible: boolean, bounce: boolean, milestone: boolean, label: string}}
 */
export function badgeView(prevCount, count) {
  const now = asCount(count);
  const visible = comboVisible(now);
  return {
    visible,
    bounce: visible && now > asCount(prevCount),
    milestone: visible && isMilestone(now),
    label: visible ? `${now}콤보` : "",
  };
}

/**
 * 이벤트에 어떤 효과음을 낼지 정한다 (정책의 단일 위치).
 * - 정답: 마일스톤이면 milestone 하나만(정답음과 겹치지 않음), 아니면 correct
 * - 오답: 4지선다 퀴즈에서만 wrong
 * - 플래시카드: "알아요"·"헷갈려요" 모두 무음 (완료 팡파레만 낸다)
 * - 완료: 정상 완주이고 정답이 1개 이상일 때만 complete
 * @param {{type: "answer", mode: string, isCorrect: boolean, count: number} | {type: "complete", aborted: boolean, answered: number, correct: number} | undefined} event
 * @returns {"correct" | "milestone" | "wrong" | "complete" | null}
 */
export function soundCueFor(event) {
  if (!event) return null;
  if (event.type === "answer") {
    if (event.mode !== "quiz") return null; // 플래시카드는 답 효과음이 없다: 퀴즈 정답음과 같아 중복이고 '헷갈려요' 와도 일관된다
    if (event.isCorrect) return isMilestone(event.count) ? "milestone" : "correct";
    return "wrong";
  }
  if (event.type === "complete") {
    return !event.aborted && event.answered > 0 && event.correct >= 1 ? "complete" : null;
  }
  return null;
}
