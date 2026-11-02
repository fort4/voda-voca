/*
 * 2026-11-02 - voda-voca - 퀴즈 정답 사운드: Web Audio API 로 두 음(D5→A5)을 합성한다. 외부 오디오 파일 없음. 오답은 무음. 음소거는 localStorage 에 저장.
 * 파일 위치: src/frontend/js/core/sound.js
 */

export const SOUND_STORAGE_KEY = "voda.sound_muted";

/** 정답 효과음: 상향 두 음. 각 음은 0.15초 동안 울리고, 두 번째 음은 첫 음이 끝나기 전에 겹쳐 시작한다. */
export const CORRECT_TONES = Object.freeze([
  { frequency: 587.33, start: 0 }, // D5
  { frequency: 880.0, start: 0.08 }, // A5
]);
export const TONE_DURATION = 0.15;
const PEAK_GAIN = 0.2;
const FLOOR_GAIN = 0.0001; // exponentialRamp 은 0 을 쓸 수 없다. 이 값에서 시작·끝내 팝 노이즈를 막는다.

/**
 * 사운드 엔진. AudioContext 와 저장소는 주입받아 테스트에서 가짜로 바꾼다.
 * @param {{AudioContextCtor?: any, storage?: Storage|null, doc?: Document|null}} [deps]
 */
export function createSoundEngine({
  AudioContextCtor = globalThis.AudioContext ?? globalThis.webkitAudioContext,
  storage = globalThis.localStorage,
  doc = globalThis.document ?? null,
} = {}) {
  let context = null;
  let gestureListening = false;
  let muted = readMuted();

  function readMuted() {
    try {
      return storage ? storage.getItem(SOUND_STORAGE_KEY) === "true" : false;
    } catch {
      return false; // 저장소를 읽을 수 없으면 소리를 켠 상태로 본다
    }
  }

  function writeMuted() {
    try {
      storage?.setItem(SOUND_STORAGE_KEY, String(muted));
    } catch {
      // 저장 실패는 소리 동작을 막지 않는다
    }
  }

  /** 첫 사용자 제스처에서 멈춘 컨텍스트를 깨운다 (브라우저 자동재생 정책). */
  function listenForGesture() {
    if (gestureListening || !doc) return;
    gestureListening = true;
    const wake = () => {
      doc.removeEventListener("pointerdown", wake);
      doc.removeEventListener("keydown", wake);
      gestureListening = false;
      if (context?.state === "suspended") context.resume?.().catch(() => {});
    };
    doc.addEventListener("pointerdown", wake);
    doc.addEventListener("keydown", wake);
  }

  /** @returns {any|null} 컨텍스트. 지원하지 않는 브라우저면 null. */
  function ensureContext() {
    if (context) return context;
    if (typeof AudioContextCtor !== "function") return null;
    try {
      context = new AudioContextCtor();
    } catch {
      return null;
    }
    return context;
  }

  return {
    /** 음소거 여부 (true 면 소리가 나지 않는다). */
    isMuted: () => muted,

    /**
     * 음소거를 뒤집고 저장한다.
     * @returns {boolean} 바뀐 뒤의 음소거 여부
     */
    toggleMute() {
      muted = !muted;
      writeMuted();
      return muted;
    },

    /**
     * 정답 효과음을 낸다. 음소거 중이거나 Web Audio 를 쓸 수 없으면 아무것도 하지 않고 false 를 돌려준다.
     * @returns {boolean} 소리를 냈는지
     */
    playCorrect() {
      if (muted) return false;
      const audio = ensureContext();
      if (!audio) return false;
      if (audio.state === "suspended") {
        audio.resume?.().catch(() => {});
        listenForGesture();
      }
      const now = audio.currentTime;
      for (const tone of CORRECT_TONES) {
        const oscillator = audio.createOscillator();
        const gain = audio.createGain();
        oscillator.type = "sine";
        oscillator.frequency.setValueAtTime(tone.frequency, now + tone.start);
        gain.gain.setValueAtTime(FLOOR_GAIN, now + tone.start);
        gain.gain.exponentialRampToValueAtTime(PEAK_GAIN, now + tone.start + 0.01);
        gain.gain.exponentialRampToValueAtTime(FLOOR_GAIN, now + tone.start + TONE_DURATION);
        oscillator.connect(gain);
        gain.connect(audio.destination);
        oscillator.start(now + tone.start);
        oscillator.stop(now + tone.start + TONE_DURATION + 0.02);
      }
      return true;
    },
  };
}

/** 앱 전체가 쓰는 엔진. 오답 효과음은 일부러 두지 않는다 (무음). */
export const sound = createSoundEngine();

export const isMuted = () => sound.isMuted();
export const toggleMute = () => sound.toggleMute();
export const playCorrect = () => sound.playCorrect();
