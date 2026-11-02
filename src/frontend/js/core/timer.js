/*
 * 2026-11-02 - voda-voca - 세션 카운트다운 계산: 서버 Date 헤더로 시계 차이 보정, 잔여 시간, mm:ss 표시, 5분 경고 (UI 설계서 §3.5.1, API 규격 §6)
 * 파일 위치: src/frontend/js/core/timer.js
 */

export const WARNING_MS = 5 * 60 * 1000;

/**
 * 서버 시각과 기기 시각의 차이(서버 - 기기, ms). Date 헤더가 없거나 잘못되면 0 이다.
 * @param {string|null} dateHeader RFC 1123 형식의 Date 헤더 값
 * @param {number} clientNowMs 응답을 받은 순간의 기기 시각 (Date.now())
 * @returns {number}
 */
export function computeClockOffset(dateHeader, clientNowMs) {
  if (!dateHeader) return 0;
  const serverMs = Date.parse(dateHeader);
  if (Number.isNaN(serverMs)) return 0;
  return serverMs - clientNowMs;
}

/**
 * 만료 시각까지 남은 밀리초. 음수가 되지 않는다.
 * @param {string} expiresAtIso 서버의 UTC 시각 문자열 (예: 2026-11-02T06:00:00.000Z)
 * @param {number} clientNowMs 지금 기기 시각
 * @param {number} offsetMs computeClockOffset 결과
 * @returns {number}
 */
export function remainingMs(expiresAtIso, clientNowMs, offsetMs = 0) {
  const expiresMs = Date.parse(expiresAtIso);
  if (Number.isNaN(expiresMs)) return 0;
  return Math.max(0, expiresMs - (clientNowMs + offsetMs));
}

/**
 * 남은 시간을 mm:ss 로 보인다. 초는 올림하므로 0.2초 남아도 00:01 이다.
 * @param {number} ms
 * @returns {string}
 */
export function formatClock(ms) {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

/** @param {number} ms @returns {boolean} 5분 이하면 경고 표시 */
export function isWarning(ms) {
  return ms > 0 && ms <= WARNING_MS;
}
