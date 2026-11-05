/*
 * 2026-11-05 - voda-voca - 세션 드라이버: 상태 머신(session-runner)이 낸 효과를 API 호출로 실행하고 응답을 액션으로 되돌린다
 * 파일 위치: src/frontend/js/core/session-driver.js
 */

import { ACTION, EFFECT, initialState, reduce } from "./session-runner.js";

/**
 * 상태를 들고 있는 작은 실행기. DOM 을 모르고, 화면은 onChange 로 상태를 받아 그린다.
 * @param {{api: (path: string, options?: object) => Promise<any>, onChange?: (state: object, action: object) => void}} deps
 */
export function createSessionDriver({ api, onChange = () => {} }) {
  let state = initialState();
  let disposed = false;

  /** @param {object} action @returns {object} 적용 뒤 상태 */
  function dispatch(action) {
    if (disposed) return state;
    const out = reduce(state, action);
    const changed = out.state !== state;
    state = out.state;
    if (changed) onChange(state, action);
    for (const effect of out.effects) run(effect);
    return state;
  }

  /** @param {{type: string, [key: string]: any}} effect */
  function run(effect) {
    if (effect.type === EFFECT.CREATE_SESSION) {
      api("/study/sessions", { method: "POST", body: effect.body }).then(
        (session) => dispatch({ type: ACTION.SESSION_LOADED, requestId: effect.requestId, session }),
        (error) => dispatch({ type: ACTION.SESSION_LOAD_FAILED, requestId: effect.requestId, error }),
      );
    } else if (effect.type === EFFECT.SEND_ANSWER) {
      api(`/study/sessions/${effect.sessionId}/answer`, { method: "POST", body: effect.body }).then(
        (result) => dispatch({ type: ACTION.ANSWER_RECEIVED, result }),
        (error) => dispatch({ type: ACTION.ANSWER_FAILED, error }),
      );
    }
  }

  return {
    dispatch,
    getState: () => state,
    /** 화면을 떠날 때 부른다. 이후 도착하는 응답은 상태나 화면을 건드리지 않는다. */
    dispose: () => {
      disposed = true;
    },
  };
}
