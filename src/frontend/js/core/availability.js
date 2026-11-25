/*
 * 2026-11-26 - voda-voca - 닉네임 "중복 확인" 상태 모델: 확인한 값에만 유효, 고치면 무효, 오래된 응답 무시, 가입 제출 가능 판정 (REQ-158)
 * 파일 위치: src/frontend/js/core/availability.js
 */

import { passwordConfirmState, validateNickname, validatePassword } from "./validate.js";

/**
 * @typedef {{status: "idle"|"checking"|"available"|"taken"|"error", value: string|null, message?: string}} Availability
 */

/** 확인하지 않은 상태. 불변 객체라 같은 참조로 비교할 수 있다. */
export const IDLE = Object.freeze({ status: "idle", value: null });

/**
 * 비교용 정규형. 서버가 앞뒤 공백을 지운 값으로 중복을 판정하므로 같게 맞춘다.
 * @param {string} value
 * @returns {string}
 */
const normalize = (value) => value.trim();

/**
 * 확인을 시작한다.
 * @param {string} value 입력 칸의 현재 값
 * @returns {Availability}
 */
export function startCheck(value) {
  return { status: "checking", value: normalize(value) };
}

/**
 * 서버 응답을 반영한다. 응답이 오기 전에 값이 바뀌어 상태가 달라졌으면(오래된 응답) 상태를 그대로 둔다.
 * @param {Availability} state
 * @param {string} value 요청했던 값
 * @param {boolean} available
 * @returns {Availability}
 */
export function finishCheck(state, value, available) {
  if (state.status !== "checking" || state.value !== normalize(value)) return state;
  return { status: available ? "available" : "taken", value: state.value };
}

/**
 * 확인 실패(네트워크 오류, 429 등)를 반영한다. 오래된 응답은 무시한다.
 * @param {Availability} state
 * @param {string} value
 * @param {string} message 화면에 보일 문구
 * @returns {Availability}
 */
export function failCheck(state, value, message) {
  if (state.status !== "checking" || state.value !== normalize(value)) return state;
  return { status: "error", value: state.value, message };
}

/**
 * 입력 값이 바뀌면 확인 결과를 무효로 돌린다. 앞뒤 공백만 다르면 같은 값으로 보고 유지한다.
 * @param {Availability} state
 * @param {string} current
 * @returns {Availability}
 */
export function invalidateOnEdit(state, current) {
  if (state.status === "idle") return state;
  return state.value === normalize(current) ? state : IDLE;
}

/**
 * 지금 입력 값이 "사용 가능"으로 확인된 값인가.
 * @param {Availability} state
 * @param {string} current
 * @returns {boolean}
 */
export function isConfirmed(state, current) {
  return state.status === "available" && state.value === normalize(current);
}

/**
 * 확인 결과 줄에 보일 문구와 색조.
 * @param {Availability} state
 * @returns {{text: string, tone: "ok"|"bad"|"neutral"}}
 */
export function checkResultText(state) {
  switch (state.status) {
    case "checking":
      return { text: "확인하는 중…", tone: "neutral" };
    case "available":
      return { text: "사용할 수 있는 닉네임입니다.", tone: "ok" };
    case "taken":
      return { text: "이미 사용 중인 닉네임입니다.", tone: "bad" };
    case "error":
      return { text: state.message ?? "확인하지 못했습니다. 잠시 후 다시 시도해 주세요.", tone: "bad" };
    default:
      return { text: "", tone: "neutral" };
  }
}

/**
 * 가입하기 버튼을 켤 수 있는지 판정한다. 값 자체의 오류를 먼저 알리고, 그다음 확인 여부를 본다.
 * 서버는 확인 여부와 무관하게 가입 때 중복을 다시 검사한다.
 * @param {{nickname: string, password: string, confirm: string}} values
 * @param {{nicknameState: Availability}} states
 * @returns {{ok: boolean, reason: string|null}}
 */
export function canSubmitSignup(values, { nicknameState }) {
  const reason =
    validateNickname(values.nickname) ??
    validatePassword(values.password) ??
    (passwordConfirmState(values.password, values.confirm).kind === "match" ? null : "비밀번호가 일치하지 않습니다.") ??
    (isConfirmed(nicknameState, values.nickname) ? null : "닉네임 중복 확인을 해 주세요.");
  return { ok: reason === null, reason };
}
