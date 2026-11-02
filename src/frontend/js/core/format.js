/*
 * 2026-11-02 - voda-voca - 표시용 포맷터: 한국 시각 변환, 재시도 대기 문구, UTF-8 바이트 길이 (REQ-109, REQ-121)
 * 파일 위치: src/frontend/js/core/format.js
 */

const KST_FORMATTER = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/**
 * 서버의 UTC 시각 문자열(Z 접미사)을 한국 시각 문자열로 바꾼다.
 * @param {string} iso
 * @returns {string} 잘못된 값이면 빈 문자열
 */
export function formatKst(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return KST_FORMATTER.format(date);
}

/**
 * 429 대기 안내 문구.
 * @param {number} seconds
 * @returns {string}
 */
export function formatRetry(seconds) {
  const s = Math.max(1, Math.ceil(seconds));
  return `약 ${s}초 후 다시 시도할 수 있습니다.`;
}

/**
 * 문자열의 UTF-8 바이트 길이. 비밀번호 72바이트 제한 검사에 쓴다.
 * @param {string} text
 * @returns {number}
 */
export function utf8ByteLength(text) {
  return new TextEncoder().encode(text).length;
}

const KST_PARTS = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/**
 * UTC 시각을 한국 날짜 키(YYYY-MM-DD)로 바꾼다. 날짜 묶음에 쓴다.
 * @param {string} iso
 * @returns {string} 잘못된 값이면 빈 문자열
 */
export function kstDateKey(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return KST_PARTS.format(date);
}

/**
 * 한국 시각의 시:분 (HH:mm).
 * @param {string} iso
 * @returns {string}
 */
export function kstTime(iso) {
  const full = formatKst(iso);
  const match = /(\d{2}:\d{2})$/.exec(full);
  return match ? match[1] : "";
}
