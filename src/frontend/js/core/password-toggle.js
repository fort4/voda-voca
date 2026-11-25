/*
 * 2026-11-25 - voda-voca - 비밀번호 보기/숨기기 토글 상태 모델: 입력 type, 버튼 라벨, aria-pressed, 아이콘 이름 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/password-toggle.js
 */

/**
 * @param {boolean} visible 비밀번호를 화면에 보여 주는 중이면 true
 * @returns {{type: "password"|"text", label: string, pressed: "true"|"false", iconName: "eye"|"eye-off"}}
 */
export function passwordToggleState(visible) {
  return visible
    ? { type: "text", label: "비밀번호 숨기기", pressed: "true", iconName: "eye-off" }
    : { type: "password", label: "비밀번호 보기", pressed: "false", iconName: "eye" };
}
