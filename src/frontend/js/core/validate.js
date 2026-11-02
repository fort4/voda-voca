/*
 * 2026-11-02 - voda-voca - 입력 검증 규칙: 서버 스키마(REQ-111)와 같은 제한값을 전송 전에 확인한다. 순수 함수.
 * 파일 위치: src/frontend/js/core/validate.js
 */

import { utf8ByteLength } from "./format.js";

export const LIMITS = Object.freeze({
  EMAIL_MAX: 255,
  PASSWORD_MIN: 8,
  PASSWORD_MAX_BYTES: 72,
  NICKNAME_MAX: 50,
  WORDBOOK_NAME_MAX: 50,
  WORDBOOK_DESCRIPTION_MAX: 200,
  WORD_TERM_MAX: 100,
  WORD_MEANING_MAX: 200,
  WORD_EXAMPLE_MAX: 500,
});

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** @param {string} value @returns {string|null} 오류 문구 또는 null */
export function validateEmail(value) {
  const email = value.trim();
  if (!email) return "이메일을 입력해 주세요.";
  if (email.length > LIMITS.EMAIL_MAX) return `이메일은 ${LIMITS.EMAIL_MAX}자 이하여야 합니다.`;
  if (!EMAIL_PATTERN.test(email)) return "이메일 형식이 올바르지 않습니다.";
  return null;
}

/** @param {string} value @returns {string|null} */
export function validatePassword(value) {
  if (value.length < LIMITS.PASSWORD_MIN) return `비밀번호는 ${LIMITS.PASSWORD_MIN}자 이상이어야 합니다.`;
  if (utf8ByteLength(value) > LIMITS.PASSWORD_MAX_BYTES) {
    return `비밀번호는 ${LIMITS.PASSWORD_MAX_BYTES}바이트(한글 약 24자) 이하여야 합니다.`;
  }
  return null;
}

/** @param {string} value @returns {string|null} */
export function validateNickname(value) {
  const nickname = value.trim();
  if (!nickname) return "닉네임을 입력해 주세요.";
  if (nickname.length > LIMITS.NICKNAME_MAX) return `닉네임은 ${LIMITS.NICKNAME_MAX}자 이하여야 합니다.`;
  return null;
}

/** @param {string} value @returns {string|null} */
export function validateWordbookName(value) {
  const name = value.trim();
  if (!name) return "단어장 이름을 입력해 주세요.";
  if (name.length > LIMITS.WORDBOOK_NAME_MAX) return `단어장 이름은 ${LIMITS.WORDBOOK_NAME_MAX}자 이하여야 합니다.`;
  return null;
}

/** @param {string} value @returns {string|null} */
export function validateWordbookDescription(value) {
  if (value.trim().length > LIMITS.WORDBOOK_DESCRIPTION_MAX) {
    return `설명은 ${LIMITS.WORDBOOK_DESCRIPTION_MAX}자 이하여야 합니다.`;
  }
  return null;
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

/** @param {string} value @returns {string|null} 표제어 1~100자, 공백만 불가 */
export function validateWordTerm(value) {
  const term = value.trim();
  if (!term) return "표제어를 입력해 주세요.";
  if (term.length > LIMITS.WORD_TERM_MAX) return `표제어는 ${LIMITS.WORD_TERM_MAX}자 이하여야 합니다.`;
  return null;
}

/** @param {string} value @returns {string|null} 뜻 1~200자, 공백만 불가 */
export function validateWordMeaning(value) {
  const meaning = value.trim();
  if (!meaning) return "뜻을 입력해 주세요.";
  if (meaning.length > LIMITS.WORD_MEANING_MAX) return `뜻은 ${LIMITS.WORD_MEANING_MAX}자 이하여야 합니다.`;
  return null;
}

/** @param {string} value @returns {string|null} 예문 0~500자, 빈 값 허용 */
export function validateWordExample(value) {
  if (value.trim().length > LIMITS.WORD_EXAMPLE_MAX) return `예문은 ${LIMITS.WORD_EXAMPLE_MAX}자 이하여야 합니다.`;
  return null;
}
