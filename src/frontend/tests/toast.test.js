/*
 * 2026-11-02 - voda-voca - 토스트 래퍼 단위 테스트: 기본 옵션, 진행 막대, 커스텀 클래스, Swal 부재 시 무동작 (v1.1)
 * 파일 위치: src/frontend/tests/toast.test.js
 */

import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { toast } from "../js/core/toast.js";

afterEach(() => {
  delete globalThis.Swal;
});

test("toast 는 SweetAlert2 토스트 옵션(상단, 1.2초 자동 종료, 진행 막대 없음, voda-voca 클래스)으로 호출한다", () => {
  const calls = [];
  globalThis.Swal = { fire: (opts) => calls.push(opts) };
  toast("로그아웃되었습니다.", "info");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].toast, true);
  assert.equal(calls[0].position, "top");
  assert.equal(calls[0].timer, 1200);
  assert.equal(calls[0].timerProgressBar, false);
  assert.equal(calls[0].showConfirmButton, false);
  assert.deepEqual(calls[0].customClass, { container: "voda-toast-container", popup: "voda-toast" });
  assert.equal(calls[0].icon, "info");
  assert.equal(calls[0].title, "로그아웃되었습니다.");
});

test("icon 을 생략하면 success 로 보인다", () => {
  const calls = [];
  globalThis.Swal = { fire: (opts) => calls.push(opts) };
  toast("환영합니다!");
  assert.equal(calls[0].icon, "success");
});

test("Swal 이 없으면 아무 일도 일어나지 않고 예외도 없다", () => {
  assert.doesNotThrow(() => toast("안녕"));
});
