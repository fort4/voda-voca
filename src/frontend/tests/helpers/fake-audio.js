/*
 * 2026-11-05 - voda-voca - Web Audio 테스트용 목: AudioContext/Oscillator/Gain 을 기록용 가짜로 대체한다 (sound.test.js 에서 추출, v2.2)
 * 파일 위치: src/frontend/tests/helpers/fake-audio.js
 */

class FakeParam {
  constructor() {
    this.events = [];
    this.value = 1; // AudioParam.value 대입(마스터 게인 등)을 받는다
  }
  setValueAtTime(value, at) {
    this.events.push({ kind: "set", value, at });
  }
  exponentialRampToValueAtTime(value, at) {
    this.events.push({ kind: "ramp", value, at });
  }
  linearRampToValueAtTime(value, at) {
    this.events.push({ kind: "linear", value, at });
  }
}

class FakeOscillator {
  constructor(ctx) {
    this.type = "";
    this.frequency = new FakeParam();
    this.started = null;
    this.stopped = null;
    this.connected = null;
    this.disconnected = false;
    this.onended = null;
    ctx.oscillators.push(this);
  }
  disconnect() {
    this.disconnected = true;
  }
  /** 재생이 끝났다고 알린다 (브라우저의 ended 이벤트). */
  end() {
    this.onended?.({});
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
    this.disconnected = false;
    ctx.gains.push(this);
  }
  disconnect() {
    this.disconnected = true;
  }
  connect(node) {
    this.connected = node;
  }
}

export function fakeContextClass() {
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
