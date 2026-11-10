/*
 * 2026-11-10 - voda-voca - 학습 설정 저장소: 사용자별 캐시, 낙관적 변경과 롤백, 구독 알림. 헤더 모달과 홈이 같은 값을 본다 (REQ-147)
 * 파일 위치: src/frontend/js/core/settings-store.js
 */

import { api as realApi } from "./api.js";
import { FALLBACK_SETTINGS, applySetting, normalizeSettings } from "./settings-model.js";

const PATH = "/users/me/settings";

/**
 * @param {{api: (path: string, options?: object) => Promise<any>}} deps 테스트에서 api 를 바꿔 끼운다
 */
export function createSettingsStore({ api }) {
  let settings = FALLBACK_SETTINGS;
  /** @type {number|null} 캐시가 속한 사용자. 다른 사용자가 오면 버린다 */
  let ownerId = null;
  /** @type {Promise<typeof settings>|null} */
  let inflight = null;
  const listeners = new Set();

  const notify = () => listeners.forEach((listener) => listener(settings));

  function reset() {
    settings = FALLBACK_SETTINGS;
    ownerId = null;
    inflight = null;
    notify();
  }

  /**
   * 서버에서 설정을 받는다. 같은 사용자는 한 번만 받고, 동시에 불러도 요청은 하나다.
   * 실패하면 거부하며 다음 호출에서 다시 시도한다.
   * @param {number} userId
   */
  function load(userId) {
    if (ownerId !== null && ownerId !== userId) {
      settings = FALLBACK_SETTINGS;
      ownerId = null;
      inflight = null;
    }
    if (ownerId === userId) return inflight ?? Promise.resolve(settings);
    ownerId = userId;
    const request = api(PATH).then(
      (raw) => {
        if (ownerId !== userId) return settings; // 받는 사이 사용자가 바뀌었다
        settings = normalizeSettings(raw);
        notify();
        return settings;
      },
      (error) => {
        if (ownerId === userId) {
          ownerId = null;
          inflight = null;
        }
        throw error;
      },
    );
    inflight = request;
    return request;
  }

  /**
   * 한 항목을 바꾼다. 먼저 반영하고 저장하며, 실패하면 이전 값으로 되돌린다
   * (그 사이 다른 값으로 다시 고른 경우에는 건드리지 않는다).
   * @param {string} key
   * @param {number} value
   * @returns {Promise<boolean>} 저장 성공(또는 변경 없음) 여부
   */
  async function change(key, value) {
    const previous = settings[key];
    const next = applySetting(settings, key, value);
    if (next === settings) return true;
    settings = next;
    notify();
    try {
      await api(PATH, { method: "PATCH", body: { [key]: value } });
      return true;
    } catch {
      if (settings[key] === value) {
        settings = applySetting(settings, key, previous);
        notify();
      }
      return false;
    }
  }

  /** @param {(settings: typeof FALLBACK_SETTINGS) => void} listener @returns {() => void} 해제 함수 */
  function subscribe(listener) {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  return { get: () => settings, load, change, subscribe, reset };
}

/** 앱 전체가 공유하는 인스턴스 */
export const settingsStore = createSettingsStore({ api: realApi });
