/*
 * 2026-11-05 - voda-voca - 세션 효과음: Web Audio API 로 정답(아르페지오)·콤보 마일스톤(4음 상승)·오답(저음 드롭)·세션 완료(팡파레)를 합성한다. 외부 오디오 파일 없음. 음소거는 localStorage 에 저장 (v2.2, REQ-137 개정)
 * 파일 위치: src/frontend/js/core/sound.js
 */

export const SOUND_STORAGE_KEY = "voda.sound_muted";

/** 모든 음이 거치는 마스터 게인. 화음·겹침이 클리핑되지 않도록 여유를 둔다. */
export const MASTER_GAIN = 0.6;
/** 각 음이 끝난 뒤 오실레이터를 멈추기까지의 여유(초). */
export const STOP_MARGIN = 0.02;
const FLOOR_GAIN = 0.0001; // exponentialRamp 은 0 을 쓸 수 없다. 이 값에서 시작·끝내 팝 노이즈를 막는다.
const DEFAULT_ATTACK = 0.01;

/**
 * 음 하나. start 는 큐 시작 기준(초), duration 은 울림 길이, peak 는 최대 음량(마스터 게인 앞).
 * endFrequency 가 있으면 frequency 에서 거기까지 지수로 미끄러진다.
 * @typedef {{type: "sine" | "triangle", frequency: number, endFrequency?: number, start: number, duration: number, peak: number, attack?: number}} Voice
 */

// 음 높이: C5 523.25, E5 659.25, G5 783.99, C6 1046.5, G4 392
/** @type {Readonly<Record<"correct" | "milestone" | "wrong" | "complete", {voices: readonly Voice[]}>>} */
export const CUES = Object.freeze({
  // 정답: 상승 아르페지오
  correct: {
    voices: [
      { type: "sine", frequency: 523.25, start: 0, duration: 0.18, peak: 0.2 },
      { type: "sine", frequency: 659.25, start: 0.07, duration: 0.18, peak: 0.2 },
      { type: "sine", frequency: 783.99, start: 0.14, duration: 0.18, peak: 0.2 },
    ],
  },
  // 콤보 마일스톤: 4음 상승. 마지막 C6 는 길게, 삼각파를 살짝 겹쳐 밝게
  milestone: {
    voices: [
      { type: "sine", frequency: 523.25, start: 0, duration: 0.18, peak: 0.2 },
      { type: "sine", frequency: 659.25, start: 0.08, duration: 0.18, peak: 0.2 },
      { type: "sine", frequency: 783.99, start: 0.16, duration: 0.18, peak: 0.2 },
      { type: "sine", frequency: 1046.5, start: 0.24, duration: 0.4, peak: 0.2 },
      { type: "triangle", frequency: 1046.5, start: 0.24, duration: 0.4, peak: 0.06 },
    ],
  },
  // 오답: 낮고 부드럽게 가라앉는 한 음 (느린 어택, 낮은 음량)
  wrong: {
    voices: [{ type: "sine", frequency: 196, endFrequency: 130.8, start: 0, duration: 0.25, peak: 0.12, attack: 0.03 }],
  },
  // 세션 완료: G4-C5-E5-G5 로 오른 뒤 C5+E5+G5 화음을 길게
  complete: {
    voices: [
      { type: "triangle", frequency: 392, start: 0, duration: 0.14, peak: 0.16 },
      { type: "triangle", frequency: 523.25, start: 0.12, duration: 0.14, peak: 0.16 },
      { type: "triangle", frequency: 659.25, start: 0.24, duration: 0.14, peak: 0.16 },
      { type: "triangle", frequency: 783.99, start: 0.36, duration: 0.14, peak: 0.16 },
      { type: "triangle", frequency: 523.25, start: 0.5, duration: 0.6, peak: 0.1 },
      { type: "triangle", frequency: 659.25, start: 0.5, duration: 0.6, peak: 0.1 },
      { type: "triangle", frequency: 783.99, start: 0.5, duration: 0.6, peak: 0.1 },
    ],
  },
});

export const CUE_NAMES = Object.freeze(Object.keys(CUES));

/**
 * 같은 순간에 울리는 음들의 최대 음량 합 (보수적: 각 음이 울리는 내내 최대 음량이라고 본다).
 * 마스터 게인을 곱해 1 아래인지로 클리핑 여유를 검증한다.
 * @param {{voices: readonly {start: number, duration: number, peak: number}[]}} cue
 * @returns {number}
 */
export function maxOverlapPeak(cue) {
  let max = 0;
  for (const probe of cue.voices) {
    // 합이 최대가 되는 순간은 어떤 음이 시작하는 시각이다
    const sum = cue.voices.filter((v) => v.start <= probe.start && probe.start < v.start + v.duration).reduce((acc, v) => acc + v.peak, 0);
    max = Math.max(max, sum);
  }
  return max;
}

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
  let master = null;
  let gestureListening = false;
  let muted = readMuted();
  const listeners = new Set();

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

  /** 모든 음이 거치는 마스터 게인을 컨텍스트당 한 번만 만든다. */
  function ensureMaster(audio) {
    if (master) return master;
    master = audio.createGain();
    master.gain.value = MASTER_GAIN;
    master.connect(audio.destination);
    return master;
  }

  /** 음 하나를 예약한다: 오실레이터 → 개별 게인(지수 엔벨로프) → 마스터. 끝나면 연결을 풀어 정리한다. */
  function scheduleVoice(audio, out, now, voice) {
    const at = now + voice.start;
    const end = at + voice.duration;
    const oscillator = audio.createOscillator();
    const gain = audio.createGain();
    oscillator.type = voice.type;
    oscillator.frequency.setValueAtTime(voice.frequency, at);
    if (voice.endFrequency) oscillator.frequency.exponentialRampToValueAtTime(voice.endFrequency, end);
    gain.gain.setValueAtTime(FLOOR_GAIN, at);
    gain.gain.exponentialRampToValueAtTime(voice.peak, at + (voice.attack ?? DEFAULT_ATTACK));
    gain.gain.exponentialRampToValueAtTime(FLOOR_GAIN, end);
    oscillator.connect(gain);
    gain.connect(out);
    oscillator.onended = () => {
      oscillator.disconnect?.();
      gain.disconnect?.();
    };
    oscillator.start(at);
    oscillator.stop(end + STOP_MARGIN);
  }

  const engine = {
    /** 음소거 여부 (true 면 소리가 나지 않는다). */
    isMuted: () => muted,

    /**
     * 음소거를 뒤집고 저장한 뒤 구독자에게 알린다.
     * @returns {boolean} 바뀐 뒤의 음소거 여부
     */
    toggleMute() {
      muted = !muted;
      writeMuted();
      for (const listener of [...listeners]) {
        try {
          listener(muted);
        } catch {
          // 구독자의 오류가 토글을 막지 않는다
        }
      }
      return muted;
    },

    /**
     * 음소거가 바뀔 때마다 새 상태(true=음소거)를 알려 줄 함수를 등록한다. 토글 버튼이 여러 곳일 때 쓴다.
     * @param {(muted: boolean) => void} listener
     * @returns {() => void} 구독 해제
     */
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    /**
     * 효과음 큐를 낸다. 음소거 중이거나 Web Audio 를 쓸 수 없거나 큐 이름을 모르면 아무것도 하지 않고 false.
     * 어떤 경우에도 예외를 던지지 않는다.
     * @param {string} name correct | milestone | wrong | complete
     * @returns {boolean} 소리를 냈는지
     */
    playCue(name) {
      if (muted || !Object.hasOwn(CUES, name)) return false;
      try {
        const audio = ensureContext();
        if (!audio) return false;
        if (audio.state === "suspended") {
          audio.resume?.().catch(() => {});
          listenForGesture();
        }
        const out = ensureMaster(audio);
        const now = audio.currentTime;
        for (const voice of CUES[/** @type {keyof typeof CUES} */ (name)].voices) scheduleVoice(audio, out, now, voice);
        return true;
      } catch {
        return false;
      }
    },

    /** 정답 효과음 (기존 호출처 호환: playCue("correct") 의 별칭). */
    playCorrect() {
      return engine.playCue("correct");
    },
  };
  return engine;
}

/** 앱 전체가 쓰는 엔진. */
export const sound = createSoundEngine();

export const isMuted = () => sound.isMuted();
export const toggleMute = () => sound.toggleMute();
/** @param {(muted: boolean) => void} listener @returns {() => void} */
export const subscribeMute = (listener) => sound.subscribe(listener);
/** @param {string} name @returns {boolean} */
export const playCue = (name) => sound.playCue(name);
export const playCorrect = () => sound.playCue("correct");
