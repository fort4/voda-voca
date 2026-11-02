/*
 * 2026-11-02 - voda-voca - 정답 사운드 엔진 단위 테스트: 두 음 합성(주파수, 시각, 감쇠), 음소거 토글과 저장, 음소거 시 무동작, suspended 컨텍스트 재개, 오답 무음 (AudioContext 는 가짜로 대체)
 * 파일 위치: src/frontend/tests/sound.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createSoundEngine, CORRECT_TONES, SOUND_STORAGE_KEY, TONE_DURATION } from "../js/core/sound.js";

class FakeParam {
  constructor() {
    this.events = [];
  }
  setValueAtTime(value, at) {
    this.events.push({ kind: "set", value, at });
  }
  exponentialRampToValueAtTime(value, at) {
    this.events.push({ kind: "ramp", value, at });
  }
}

class FakeOscillator {
  constructor(ctx) {
    this.type = "";
    this.frequency = new FakeParam();
    this.started = null;
    this.stopped = null;
    this.connected = null;
    ctx.oscillators.push(this);
  }
  connect(node) {
    this.connected = node;
  }
  start(at) {
    this.started = at;
  }
  stop(at) {
    this.stopped = at;
  }
}

class FakeGain {
  constructor(ctx) {
    this.gain = new FakeParam();
    this.connected = null;
    ctx.gains.push(this);
  }
  connect(node) {
    this.connected = node;
  }
}

function fakeContextClass() {
  const instances = [];
  class FakeAudioContext {
    constructor() {
      this.state = "running";
      this.currentTime = 10;
      this.destination = { name: "speakers" };
      this.oscillators = [];
      this.gains = [];
      this.resumeCalls = 0;
      instances.push(this);
    }
    createOscillator() {
      return new FakeOscillator(this);
    }
    createGain() {
      return new FakeGain(this);
    }
    resume() {
      this.resumeCalls += 1;
      this.state = "running";
      return Promise.resolve();
    }
  }
  return { FakeAudioContext, instances };
}

function memoryStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    dump: () => Object.fromEntries(map),
  };
}

function fakeDocument() {
  const listeners = new Map();
  return {
    addEventListener(type, fn) {
      listeners.set(type, fn);
    },
    removeEventListener(type) {
      listeners.delete(type);
    },
    fire(type) {
      listeners.get(type)?.();
    },
    listening: () => [...listeners.keys()],
  };
}

test("정답 효과음은 D5(587.33Hz)와 A5(880.00Hz) 두 사인파를 순서대로 낸다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage() });

  assert.equal(engine.playCorrect(), true);
  const [ctx] = instances;
  assert.equal(ctx.oscillators.length, 2);
  assert.deepEqual(
    ctx.oscillators.map((o) => o.frequency.events[0].value),
    [587.33, 880.0],
  );
  for (const osc of ctx.oscillators) {
    assert.equal(osc.type, "sine");
    assert.equal(osc.connected, ctx.gains[ctx.oscillators.indexOf(osc)]);
  }
  for (const gain of ctx.gains) assert.equal(gain.connected, ctx.destination);
  assert.equal(CORRECT_TONES[1].frequency > CORRECT_TONES[0].frequency, true, "두 번째 음이 더 높다 (상향)");
});

test("각 음은 0.15초 울리고 현재 시각 기준으로 시작한다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage() });
  engine.playCorrect();
  const [ctx] = instances;
  ctx.oscillators.forEach((osc, i) => {
    const tone = CORRECT_TONES[i];
    assert.equal(osc.started, ctx.currentTime + tone.start);
    assert.ok(Math.abs(osc.stopped - (osc.started + TONE_DURATION + 0.02)) < 1e-9, "정지 시각은 울림 끝 + 여유 20ms");
  });
});

test("볼륨은 지수 감쇠로 바뀌고 0 이하 값이 없어 팝 노이즈를 피한다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage() });
  engine.playCorrect();
  for (const gain of instances[0].gains) {
    const values = gain.gain.events.map((e) => e.value);
    assert.ok(values.every((v) => v > 0), "지수 램프의 목표 값은 모두 양수여야 한다");
    assert.ok(gain.gain.events.every((e) => e.kind === "set" || e.kind === "ramp"));
    assert.equal(gain.gain.events.at(-1).value < 0.001, true, "끝은 거의 0으로 감쇠");
  }
});

test("toggleMute 는 상태를 뒤집고 localStorage 에 저장한다", () => {
  const storage = memoryStorage();
  const engine = createSoundEngine({ AudioContextCtor: fakeContextClass().FakeAudioContext, storage });
  assert.equal(engine.isMuted(), false);

  assert.equal(engine.toggleMute(), true);
  assert.equal(engine.isMuted(), true);
  assert.equal(storage.dump()[SOUND_STORAGE_KEY], "true");

  assert.equal(engine.toggleMute(), false);
  assert.equal(engine.isMuted(), false);
  assert.equal(storage.dump()[SOUND_STORAGE_KEY], "false");
});

test("저장된 음소거 상태를 처음부터 읽는다 (기본값은 소리 켬)", () => {
  const { FakeAudioContext } = fakeContextClass();
  assert.equal(createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage({ [SOUND_STORAGE_KEY]: "true" }) }).isMuted(), true);
  assert.equal(createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage({ [SOUND_STORAGE_KEY]: "false" }) }).isMuted(), false);
  assert.equal(createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage() }).isMuted(), false);
  assert.equal(createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: null }).isMuted(), false);
});

test("음소거 상태에서는 playCorrect 가 아무 오실레이터도 만들지 않는다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage({ [SOUND_STORAGE_KEY]: "true" }) });
  assert.equal(engine.playCorrect(), false);
  assert.equal(instances.length, 0, "컨텍스트도 만들지 않는다");
});

test("음소거를 켠 뒤 playCorrect 는 소리를 내지 않는다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage() });
  engine.toggleMute();
  assert.equal(engine.playCorrect(), false);
  assert.equal(instances.length, 0);
});

test("suspended 컨텍스트는 resume 을 호출하고, 첫 사용자 제스처에서도 다시 깨운다", () => {
  const { FakeAudioContext, instances } = fakeContextClass();
  const doc = fakeDocument();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage(), doc });
  engine.playCorrect(); // 컨텍스트 생성
  const [ctx] = instances;

  ctx.state = "suspended";
  engine.playCorrect();
  assert.ok(ctx.resumeCalls >= 1);
  assert.deepEqual(doc.listening().sort(), ["keydown", "pointerdown"]);

  ctx.state = "suspended";
  const before = ctx.resumeCalls;
  doc.fire("pointerdown");
  assert.equal(ctx.resumeCalls, before + 1);
  assert.deepEqual(doc.listening(), [], "제스처 리스너는 한 번만 쓰고 뗀다");
});

test("Web Audio 를 지원하지 않거나 컨텍스트 생성이 실패해도 예외 없이 false 를 돌려준다", () => {
  assert.equal(createSoundEngine({ AudioContextCtor: undefined, storage: memoryStorage() }).playCorrect(), false);
  class Broken {
    constructor() {
      throw new Error("no audio");
    }
  }
  assert.equal(createSoundEngine({ AudioContextCtor: Broken, storage: memoryStorage() }).playCorrect(), false);
});

test("저장소가 실패해도 토글은 동작한다", () => {
  const throwing = {
    getItem() {
      throw new Error("blocked");
    },
    setItem() {
      throw new Error("quota");
    },
  };
  const engine = createSoundEngine({ AudioContextCtor: fakeContextClass().FakeAudioContext, storage: throwing });
  assert.equal(engine.isMuted(), false);
  assert.equal(engine.toggleMute(), true);
});

test("오답 효과음은 없다 (엔진에 오답 재생 함수가 없다)", () => {
  const engine = createSoundEngine({ AudioContextCtor: fakeContextClass().FakeAudioContext, storage: memoryStorage() });
  assert.equal("playWrong" in engine, false);
  assert.equal(typeof engine.playCorrect, "function");
});
