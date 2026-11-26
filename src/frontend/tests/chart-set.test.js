/*
 * 2026-11-26 - voda-voca - 차트 수명 관리 단위 테스트: 생성, 테마 변경 시 다시 그리기, 화면을 떠날 때 정리, 라이브러리 실패 시 대체 (가짜 Chart)
 * 파일 위치: src/frontend/tests/chart-set.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createChartSet, watchDarkClass } from "../js/core/chart-set.js";

function fakeChartCtor() {
  const made = [];
  class FakeChart {
    constructor(canvas, config) {
      this.canvas = canvas;
      this.config = config;
      this.destroyed = false;
      made.push(this);
    }
    destroy() {
      this.destroyed = true;
    }
  }
  return { FakeChart, made };
}

function setup(over = {}) {
  const { FakeChart, made } = fakeChartCtor();
  let themeListener = null;
  let stopped = false;
  let color = "light";
  const set = createChartSet({
    ChartCtor: FakeChart,
    readPalette: () => ({ color }),
    observeTheme: (listener) => {
      themeListener = listener;
      return () => (stopped = true);
    },
    reducedMotion: () => false,
    ...over,
  });
  return {
    set,
    made,
    changeTheme: (next) => {
      color = next;
      themeListener();
    },
    isStopped: () => stopped,
  };
}

const build = (palette, options) => ({ palette, options });

test("mount 전에는 만들지 않고, mount 하면 등록한 캔버스마다 만든다", () => {
  const { set, made } = setup();
  const a = {};
  const b = {};
  set.add(a, build);
  set.add(b, build);
  assert.equal(made.length, 0);
  set.mount();
  assert.deepEqual(made.map((c) => c.canvas), [a, b]);
  assert.equal(made[0].config.options.animate, true);
  assert.equal(set.chartOf(b), made[1]);
});

test("동작 줄이기를 켜면 애니메이션 없이 만든다", () => {
  const { set, made } = setup({ reducedMotion: () => true });
  set.add({}, build);
  set.mount();
  assert.equal(made[0].config.options.animate, false);
});

test("테마가 바뀌면 이전 차트를 버리고 새 색으로 애니메이션 없이 다시 그린다", () => {
  const { set, made, changeTheme } = setup();
  const canvas = {};
  set.add(canvas, build);
  set.mount();
  changeTheme("dark");
  assert.equal(made.length, 2);
  assert.equal(made[0].destroyed, true);
  assert.deepEqual(made[1].config.palette, { color: "dark" });
  assert.equal(made[1].config.options.animate, false);
  assert.equal(set.chartOf(canvas), made[1]);
});

test("destroy 는 차트와 테마 감시를 모두 정리하고, 그 뒤의 mount 는 아무것도 하지 않는다", () => {
  const { set, made, isStopped } = setup();
  set.add({}, build);
  set.mount();
  set.destroy();
  assert.equal(made[0].destroyed, true);
  assert.equal(isStopped(), true);
  set.mount();
  assert.equal(made.length, 1);
});

test("라이브러리가 없으면 대체 처리를 부른다 (표를 펼친다)", () => {
  const { set } = setup({ ChartCtor: undefined });
  let failed = 0;
  set.add({}, build, () => (failed += 1));
  set.mount();
  assert.equal(failed, 1);
});

test("차트 하나가 실패해도 나머지는 그린다", () => {
  const { set, made } = setup();
  let failed = 0;
  set.add({}, () => {
    throw new Error("boom");
  }, () => (failed += 1));
  set.add({}, build);
  set.mount();
  assert.equal(failed, 1);
  assert.equal(made.length, 1);
});

test("watchDarkClass: dark 클래스가 실제로 바뀔 때만 알린다 (모달이 붙이는 다른 클래스는 무시)", () => {
  const classes = new Set();
  const root = { classList: { contains: (name) => classes.has(name) } };
  let notify;
  let disconnected = false;
  class FakeObserver {
    constructor(callback) {
      notify = callback;
    }
    observe(target, options) {
      assert.equal(target, root);
      assert.deepEqual(options, { attributes: true, attributeFilter: ["class"] });
    }
    disconnect() {
      disconnected = true;
    }
  }
  let calls = 0;
  const stop = watchDarkClass(root, FakeObserver, () => (calls += 1));
  classes.add("swal2-shown");
  notify();
  assert.equal(calls, 0);
  classes.add("dark");
  notify();
  notify();
  assert.equal(calls, 1);
  classes.delete("dark");
  notify();
  assert.equal(calls, 2);
  stop();
  assert.equal(disconnected, true);
});
