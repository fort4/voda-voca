/*
 * 2026-11-02 - voda-voca - 입력 검증 규칙: 서버 스키마(REQ-111)와 같은 제한값을 전송 전에 확인한다. 순수 함수.
 * 파일 위치: src/frontend/js/core/validate.js
 */

import { utf8ByteLength } from "./format.js";

export const LIMITS = Object.freeze({
  NICKNAME_MIN: 2,
  NICKNAME_MAX: 30,
  PASSWORD_MIN: 8,
  PASSWORD_MAX_BYTES: 72,
});

/** @param {string} value @returns {string|null} */
export function validatePassword(value) {
  if (value.length < LIMITS.PASSWORD_MIN) return `비밀번호는 ${LIMITS.PASSWORD_MIN}자 이상이어야 합니다.`;
  if (utf8ByteLength(value) > LIMITS.PASSWORD_MAX_BYTES) {
    return `비밀번호는 ${LIMITS.PASSWORD_MAX_BYTES}바이트(한글 약 24자) 이하여야 합니다.`;
  }
  return null;
}

/**
 * 닉네임: 공백 제거 후 2~30자. 로그인 식별자이며 중복될 수 없다 (회원 체계 단순화).
 * @param {string} value
 * @returns {string|null}
 */
export function validateNickname(value) {
  const nickname = value.trim();
  if (!nickname) return "닉네임을 입력해 주세요.";
  if (nickname.length < LIMITS.NICKNAME_MIN) return `닉네임은 ${LIMITS.NICKNAME_MIN}자 이상이어야 합니다.`;
  if (nickname.length > LIMITS.NICKNAME_MAX) return `닉네임은 ${LIMITS.NICKNAME_MAX}자 이하여야 합니다.`;
  return null;
}

/**
 * 회원 탈퇴 최종 확인: 입력한 글자가 닉네임과 같은지 본다 (앞뒤 공백만 무시).
 * @param {string} input
 * @param {string} nickname
 * @returns {boolean}
 */
export function nicknameConfirmationMatches(input, nickname) {
  return input.trim() === nickname;
}

/**
 * 서버 422 필드 오류를 입력 이름별 메시지 객체로 바꾼다. 어느 입력에도 속하지 않는 오류는 "_form" 키에 모은다.
 * @param {Array<{field: string|null, message: string}>} fields
 * @param {string[]} knownNames 화면에 있는 입력 이름
 * @returns {Record<string, string>}
 */
export function mapFieldErrors(fields, knownNames) {
  const out = {};
  for (const { field, message } of fields) {
    const key = field && knownNames.includes(field) ? field : "_form";
    if (!out[key]) out[key] = message;
  }
  return out;
}
