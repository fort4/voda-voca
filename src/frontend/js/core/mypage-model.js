/*
 * 2026-11-26 - voda-voca - 마이페이지 뷰모델: 계정 정보 표시, 비밀번호 변경 입력 판정, 서버 오류 배치 (DOM 없는 순수 로직, REQ-164)
 * 파일 위치: src/frontend/js/core/mypage-model.js
 */

import { kstDateKey } from "./format.js";
import { passwordConfirmState, validatePassword } from "./validate.js";

/** 서버 필드 이름 → 화면 입력 이름 */
const FIELD_INPUT = { current_password: "current", new_password: "next", new_password_confirm: "confirm" };

/**
 * @param {{nickname: string, created_at: string}} user
 * @returns {{nickname: string, initial: string, joined: string}}
 */
export function profileView(user) {
  return {
    nickname: user.nickname,
    initial: Array.from(user.nickname)[0]?.toUpperCase() ?? "?",
    joined: kstDateKey(user.created_at),
  };
}

/**
 * 보내기 전에 확인하는 규칙. 서버(REQ-164)와 같다. 문제가 없으면 빈 객체.
 * @param {{current: string, next: string, confirm: string}} values
 * @returns {{current?: string, next?: string, confirm?: string}}
 */
export function passwordChangeErrors({ current, next, confirm }) {
  const errors = {};
  if (!current) errors.current = "현재 비밀번호를 입력해 주세요.";
  const rule = validatePassword(next);
  if (rule) errors.next = rule;
  else if (next === current) errors.next = "현재 비밀번호와 다른 비밀번호를 입력해 주세요.";
  if (!confirm) errors.confirm = "새 비밀번호를 한 번 더 입력해 주세요.";
  else if (passwordConfirmState(next, confirm).kind !== "match") errors.confirm = "비밀번호가 일치하지 않습니다.";
  return errors;
}

/**
 * 실패한 응답을 어디에 보일지 정한다. 입력 칸에 속하지 않는 오류는 banner.
 * @param {{status: number, detail?: string, code?: string|null, retryAfter?: number|null, fields?: Array<{field: string|null, message: string}>}} error
 * @returns {{current?: string, next?: string, confirm?: string, banner?: string}}
 */
export function passwordChangeFailure(error) {
  if (error.code === "CURRENT_PASSWORD_MISMATCH") return { current: error.detail };
  if (error.status === 429) {
    const wait = error.retryAfter ? ` (${error.retryAfter}초 뒤에 다시 시도)` : "";
    return { banner: `${error.detail}${wait}` };
  }
  if (error.status === 422) {
    const placed = {};
    for (const { field, message } of error.fields ?? []) {
      const key = FIELD_INPUT[field] ?? "banner";
      if (!placed[key]) placed[key] = message;
    }
    return placed;
  }
  return { banner: error.detail };
}
