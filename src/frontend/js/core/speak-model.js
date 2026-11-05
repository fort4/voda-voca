/*
 * 2026-11-05 - voda-voca - 발음 버튼 표시 모델: 재생 상태→버튼 표시 변환, 구독 바인딩과 자동 해제 (DOM 없이 테스트 가능) (v2.2 TTS)
 * 파일 위치: src/frontend/js/core/speak-model.js
 */

/**
 * 재생 상태에서 이 버튼이 "재생 중" 인지 계산한다. key 가 같은 버튼만 켜진다.
 * key 가 없는 버튼은 켜지지 않는다 (key 없이 시작한 재생과 우연히 일치하는 것을 막는다).
 * @param {{status: string, key: string | null}} state
 * @param {string | null | undefined} key
 * @returns {{playing: boolean, ariaPressed: "true" | "false"}}
 */
export function speakButtonState(state, key) {
  const playing = state.status === "speaking" && key != null && state.key === key;
  return { playing, ariaPressed: playing ? "true" : "false" };
}

/**
 * @param {"word" | "sentence"} kind
 * @param {string} text
 * @returns {string} 스크린리더용 버튼 이름
 */
export function speakAriaLabel(kind, text) {
  return kind === "sentence" ? "예문 듣기" : `${text} 발음 듣기`;
}

/**
 * 재생 상태 구독과 버튼 표시를 연결한다.
 * 화면은 상태가 바뀔 때마다 다시 그려져 이전 버튼이 버려진다. 알림이 왔을 때 DOM 에서 떨어져 있는 버튼은
 * 구독을 풀어 누수를 막는다. (버튼은 같은 동기 흐름에서 만들어 붙이므로, 알림이 그 사이에 끼어들 수 없다.)
 * @param {{subscribe: (fn: (state: any) => void) => () => void, getState: () => any, key: string | null | undefined, isConnected: () => boolean, apply: (view: ReturnType<typeof speakButtonState>) => void}} deps
 * @returns {() => void} 구독 해제 함수 (여러 번 불러도 안전)
 */
export function bindSpeakState({ subscribe, getState, key, isConnected, apply }) {
  let off = /** @type {(() => void) | null} */ (null);
  const dispose = () => {
    off?.();
    off = null;
  };
  off = subscribe((state) => {
    if (!isConnected()) {
      dispose();
      return;
    }
    apply(speakButtonState(state, key));
  });
  apply(speakButtonState(getState(), key)); // 다시 그려진 시점에 이미 재생 중일 수 있다
  return dispose;
}
