/*
 * 2026-11-11 - voda-voca - 환경 설정 뷰모델: 효과음·다크 모드 스위치 행의 라벨, 설명, 상태, 아이콘 (DOM 없는 순수 로직)
 * 파일 위치: src/frontend/js/core/preferences-model.js
 */

/**
 * 환경 설정 모달의 스위치 행. 아이콘은 지금 상태를 보여 준다 (소리가 켜져 있으면 bell-ring, 다크면 moon).
 * @param {{muted: boolean, theme: "light"|"dark"}} state
 * @returns {Array<{id: "sound"|"theme", label: string, description: string, checked: boolean, icon: string}>}
 */
export function preferenceRows({ muted, theme }) {
  return [
    {
      id: "sound",
      label: "효과음",
      description: "정답·오답·콤보·완료 소리와 퀴즈 자동 발음을 들려줘요. 발음 듣기 버튼은 별개예요.",
      checked: !muted,
      icon: muted ? "bell-off" : "bell-ring",
    },
    {
      id: "theme",
      label: "다크 모드",
      description: "어두운 화면으로 바꿔요. 이 기기에 기억해 둬요.",
      checked: theme === "dark",
      icon: theme === "dark" ? "moon" : "sun",
    },
  ];
}

/**
 * 로그인 전 헤더의 다크 모드 버튼 표시. 아이콘과 라벨은 지금 상태가 아니라 **누르면 바뀔 모드**를 알려 준다
 * (라이트면 moon + "다크 모드로 전환", 다크면 sun + "라이트 모드로 전환"). 글자 없는 아이콘 버튼이라 라벨이 행동을 말해야 한다.
 * @param {string|undefined} theme 현재 테마 ("dark" 가 아니면 라이트로 본다)
 * @returns {{icon: "moon"|"sun", label: string}}
 */
export function themeToggleView(theme) {
  return theme === "dark"
    ? { icon: "sun", label: "라이트 모드로 전환" }
    : { icon: "moon", label: "다크 모드로 전환" };
}
