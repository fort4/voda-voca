/*
 * 2026-11-02 - voda-voca - 터치·포인터 제스처 판정: 좌우 스와이프(48px, 가로 우세), 탭(8px 미만 이동) (UI 설계서 §7)
 * 파일 위치: src/frontend/js/core/gesture.js
 */

export const SWIPE_MIN_PX = 48;
export const TAP_MAX_MOVE_PX = 8;

/**
 * 이동 거리로 제스처를 판정한다.
 * - 이동이 8px 미만이면 'tap' (뒤집기).
 * - 가로 이동이 48px 이상이고 세로 이동보다 크면 'next' (왼쪽으로 밀기) 또는 'prev' (오른쪽으로 밀기).
 * - 그 밖은 null (세로 스크롤과 충돌하지 않도록 무시).
 * @param {number} dx 오른쪽이 양수
 * @param {number} dy 아래가 양수
 * @returns {"tap"|"next"|"prev"|null}
 */
export function classifyGesture(dx, dy) {
  const absX = Math.abs(dx);
  const absY = Math.abs(dy);
  if (absX < TAP_MAX_MOVE_PX && absY < TAP_MAX_MOVE_PX) return "tap";
  if (absX >= SWIPE_MIN_PX && absX > absY) return dx < 0 ? "next" : "prev";
  return null;
}
