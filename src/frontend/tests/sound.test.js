/*
 * 2026-11-05 - voda-voca - 세션 효과음 엔진 단위 테스트: 큐 4종(정답 아르페지오·마일스톤·오답·완료) 합성, 마스터 게인·클리핑 방지, 음소거 토글·저장·구독, 노드 정리, 미지원 안전 (AudioContext 는 가짜로 대체)
 * 파일 위치: src/frontend/tests/sound.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { CUES, CUE_NAMES, MASTER_GAIN, SOUND_STORAGE_KEY, STOP_MARGIN, createSoundEngine, maxOverlapPeak } from "../js/core/sound.js";
import { fakeContextClass } from "./helpers/fake-audio.js";

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

/** 엔진과 가짜 컨텍스트 한 쌍을 만든다. */
function setup(overrides = {}) {
  const { FakeAudioContext, instances } = fakeContextClass();
  const engine = createSoundEngine({ AudioContextCtor: FakeAudioContext, storage: memoryStorage(), ...overrides });
  return { engine, ctx: () => instances[0], instances };
}

/** 가짜 컨텍스트에서 음 하나(오실레이터+게인) 목록을 만든다. 첫 게인은 마스터라 뺀다. */
function voicesOf(ctx) {
  const [, ...voiceGains] = ctx.gains;
  return ctx.oscillators.map((osc, i) => ({ osc, gain: voiceGains[i] }));
}

const freqs = (ctx) => ctx.oscillators.map((o) => o.frequency.events[0].value);

test("큐는 correct, milestone, wrong, complete 네 가지다", () => {
  assert.deepEqual([...CUE_NAMES], ["correct", "milestone", "wrong", "complete"]);
  assert.deepEqual(Object.keys(CUES), [...CUE_NAMES]);
});

test("correct: C5-E5-G5 상승 아르페지오 (사인파, 순서대로 시작)", () => {
  const { engine, ctx } = setup();
  assert.equal(engine.playCue("correct"), true);
  assert.deepEqual(freqs(ctx()), [523.25, 659.25, 783.99]);
  assert.ok(ctx().oscillators.every((o) => o.type === "sine"));
  const starts = ctx().oscillators.map((o) => o.started);
  assert.deepEqual(starts, [...starts].sort((x, y) => x - y), "시작 시각이 오름차순");
  assert.ok(starts[1] > starts[0] && starts[2] > starts[1]);
});

test("milestone: C5-E5-G5-C6 네 음이 오르고 마지막 음이 가장 길다", () => {
  const { engine, ctx } = setup();
  assert.equal(engine.playCue("milestone"), true);
  const main = voicesOf(ctx()).filter(({ osc }) => osc.type === "sine");
  assert.deepEqual(main.map(({ osc }) => osc.frequency.events[0].value), [523.25, 659.25, 783.99, 1046.5]);
  const lengths = main.map(({ osc }) => osc.stopped - osc.started);
  assert.equal(Math.max(...lengths), lengths.at(-1), "마지막 C6 가 가장 길게 울린다");
});

test("wrong: 196Hz 에서 130.8Hz 로 지수 하강하는 낮고 부드러운 한 음", () => {
  const { engine, ctx } = setup();
  assert.equal(engine.playCue("wrong"), true);
  assert.equal(ctx().oscillators.length, 1);
  const [{ osc, gain }] = voicesOf(ctx());
  assert.equal(osc.type, "sine");
  const [from, to] = osc.frequency.events;
  assert.deepEqual([from.kind, from.value, to.kind, to.value], ["set", 196, "ramp", 130.8]);
  assert.ok(to.at > from.at, "하강은 시간이 걸린다");
  const peak = Math.max(...gain.gain.events.map((e) => e.value));
  assert.ok(peak <= 0.15, `부드러운 음량: ${peak}`);
  const attack = gain.gain.events.find((e) => e.kind === "ramp").at - gain.gain.events[0].at;
  assert.ok(attack >= 0.02, `날카롭지 않은 어택(≥20ms): ${attack}`);
});

test("complete: 상승 음형 뒤 C5+E5+G5 화음을 함께 시작해 길게 유지한다 (삼각파)", () => {
  const { engine, ctx } = setup();
  assert.equal(engine.playCue("complete"), true);
  assert.ok(ctx().oscillators.every((o) => o.type === "triangle"));
  const chord = ctx().oscillators.filter((o) => [523.25, 659.25, 783.99].includes(o.frequency.events[0].value) && o.started === ctx().currentTime + CUES.complete.voices.at(-1).start);
  assert.equal(chord.length, 3, "화음 세 음이 같은 시각에 시작");
  assert.ok(chord.every((o) => o.stopped - o.started >= 0.5), "화음은 0.5초 이상 유지");
  assert.equal(freqs(ctx())[0], 392, "G4 로 시작해 오른다");
});

test("각 음은 현재 시각 기준 start 에 시작하고 duration + 20ms 뒤 정지한다", () => {
  for (const name of CUE_NAMES) {
    const { engine, ctx } = setup();
    engine.playCue(name);
    ctx().oscillators.forEach((osc, i) => {
      const voice = CUES[name].voices[i];
      assert.equal(osc.started, ctx().currentTime + voice.start, name);
      assert.ok(Math.abs(osc.stopped - (osc.started + voice.duration + STOP_MARGIN)) < 1e-9, name);
    });
    assert.equal(ctx().oscillators.length, CUES[name].voices.length, name);
  }
});

test("볼륨은 0 이하 값 없이 지수로 올랐다 내려 팝 노이즈가 없고, 최대값은 큐 데이터와 같다", () => {
  for (const name of CUE_NAMES) {
    const { engine, ctx } = setup();
    engine.playCue(name);
    voicesOf(ctx()).forEach(({ gain }, i) => {
      const events = gain.gain.events;
      assert.ok(events.every((e) => e.value > 0), `${name}: 지수 램프 목표는 모두 양수`);
      assert.ok(events.every((e) => e.kind === "set" || e.kind === "ramp"), name);
      assert.ok(events[0].value < 0.001, `${name}: 시작은 거의 0`);
      assert.ok(events.at(-1).value < 0.001, `${name}: 끝은 거의 0`);
      assert.equal(Math.max(...events.map((e) => e.value)), CUES[name].voices[i].peak, `${name}: 최대 음량이 큐 데이터와 일치`);
    });
  }
});

test("모든 음은 마스터 게인을 거쳐 destination 으로 간다 (마스터는 컨텍스트당 하나, 재사용)", () => {
  const { engine, ctx } = setup();
  engine.playCue("correct");
  engine.playCue("milestone");
  const [master, ...rest] = ctx().gains;
  assert.equal(master.connected, ctx().destination);
  assert.equal(master.gain.value, MASTER_GAIN);
  assert.ok(MASTER_GAIN < 1, "여유(헤드룸)를 둔다");
  assert.ok(rest.length === 3 + CUES.milestone.voices.length, "마스터는 한 번만 만든다");
  for (const { osc, gain } of voicesOf(ctx())) {
    assert.equal(osc.connected, gain);
    assert.equal(gain.connected, master);
  }
});

test("클리핑 방지: 같은 순간 울리는 음량의 합 × 마스터 게인 이 1 을 넘지 않는다", () => {
  for (const name of CUE_NAMES) {
    const total = maxOverlapPeak(CUES[name]) * MASTER_GAIN;
    assert.ok(total <= 0.9, `${name}: 최대 합성 음량 ${total.toFixed(3)}`);
  }
});

test("maxOverlapPeak: 겹치는 음만 더한다", () => {
  const cue = { voices: [{ start: 0, duration: 1, peak: 0.2 }, { start: 0.5, duration: 1, peak: 0.3 }, { start: 2, duration: 1, peak: 0.9 }] };
  assert.ok(Math.abs(maxOverlapPeak(cue) - 0.9) < 1e-9, "마지막 음은 앞선 음과 겹치지 않아 단독 0.9");
  assert.ok(Math.abs(maxOverlapPeak({ voices: cue.voices.slice(0, 2) }) - 0.5) < 1e-9, "0.5~1.0 구간에서 0.2+0.3");
});

test("음이 끝나면(onended) 오실레이터와 게인을 연결 해제해 정리한다", () => {
  const { engine, ctx } = setup();
  engine.playCue("correct");
  const [{ osc, gain }] = voicesOf(ctx());
  assert.equal(osc.disconnected, false);
  osc.end();
  assert.equal(osc.disconnected, true);
  assert.equal(gain.disconnected, true);
});

test("알 수 없는 큐 이름은 아무 소리도 내지 않고 false", () => {
  const { engine, instances } = setup();
  assert.equal(engine.playCue("nope"), false);
  assert.equal(engine.playCue(undefined), false);
  assert.equal(instances.length === 0 || instances[0].oscillators.length === 0, true);
});

test("playCorrect 는 playCue('correct') 의 별칭이다 (기존 호출처 호환)", () => {
  const { engine, ctx } = setup();
  assert.equal(engine.playCorrect(), true);
  assert.deepEqual(freqs(ctx()), [523.25, 659.25, 783.99]);
});

test("음소거 상태에서는 어떤 큐도 오실레이터를 만들지 않는다", () => {
  const { engine, instances } = setup({ storage: memoryStorage({ [SOUND_STORAGE_KEY]: "true" }) });
  for (const name of CUE_NAMES) assert.equal(engine.playCue(name), false, name);
  assert.equal(instances.length === 0 || instances[0].oscillators.length === 0, true);
});

test("오디오 노드 생성이 예외를 던져도 false 를 돌려주고 던지지 않는다", () => {
  const { FakeAudioContext } = fakeContextClass();
  class Broken extends FakeAudioContext {
    createOscillator() {
      throw new Error("boom");
    }
  }
  const engine = createSoundEngine({ AudioContextCtor: Broken, storage: memoryStorage() });
  assert.doesNotThrow(() => engine.playCue("correct"));
  assert.equal(engine.playCue("wrong"), false);
});

test("subscribe: 음소거가 바뀔 때마다 새 상태로 알리고, 해제하면 알리지 않으며, 구독자 예외는 삼킨다", () => {
  const { engine } = setup();
  const seen = [];
  const off = engine.subscribe((muted) => seen.push(muted));
  engine.subscribe(() => {
    throw new Error("listener boom");
  });
  assert.equal(engine.toggleMute(), true);
  assert.equal(engine.toggleMute(), false);
  off();
  engine.toggleMute();
  assert.deepEqual(seen, [true, false]);
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
