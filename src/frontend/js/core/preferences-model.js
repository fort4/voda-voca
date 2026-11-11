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
      description: "정답·오답·콤보·완료 소리를 들려줘요. 발음 듣기와는 별개예요.",
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
