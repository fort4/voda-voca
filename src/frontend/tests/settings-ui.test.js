/*
 * 2026-11-10 - voda-voca - 학습 설정 UI 배선 테스트: 계정 메뉴 → 모달, 공유 저장소, 옵션 하드코딩 금지, 터치 크기, 계정 전환 시 초기화, 옛 상수 제거 (REQ-147)
 * 파일 위치: src/frontend/tests/settings-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const stripComments = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "");
const form = read("js/views/components/settings-form.js");
const modal = read("js/views/settings-modal.js");
const home = read("js/views/home-view.js");
const app = read("js/app.js");

/** @param {string} dir @returns {string[]} */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

test("설정 폼: 칩은 서버가 준 옵션으로 만들고 10/20/30 을 직접 적지 않는다", () => {
  assert.match(form, /settings\.options\.map/);
  assert.doesNotMatch(stripComments(form), /\b(10|20|30)\b/);
});

test("설정 폼: 칩은 기존 .chip 컴포넌트에 aria-pressed 로 선택을 나타내고 터치 높이 44px 이상", () => {
  assert.match(form, /class: "chip [^"]*min-h-\[44px\]/);
  assert.match(form, /"aria-pressed"/);
  assert.match(form, /SETTING_ROWS\.map/, "퀴즈·플래시카드·오늘의 목표 행은 모델 정의를 그대로 쓴다");
});

test("옛 홈 설정 카드는 없다 (헤더 모달로 옮겼다)", () => {
  assert.equal(existsSync(join(ROOT, "js/views/components/settings-card.js")), false);
  assert.doesNotMatch(home, /renderSettingsCard|settings-card/);
});

test("계정 메뉴: '학습 설정' 항목이 로그아웃보다 위에 있고 모달을 연다", () => {
  assert.match(app, /menuItem\("book-open", "학습 설정", openSettingsFromMenu\)/);
  assert.ok(app.indexOf('"학습 설정"') < app.indexOf('"로그아웃"'), "로그아웃 위에 둔다");
  assert.match(app, /function openSettingsFromMenu\(\)[\s\S]*?closeAccountMenu\(\);[\s\S]*?openSettingsModal\(\)/);
});

test("모달: SweetAlert2 로 열고, 닫기 버튼만 두며, 저장소의 값을 보고 바꾼다", () => {
  assert.match(modal, /Swal\.fire\(/);
  assert.match(modal, /title: "학습 설정"/);
  assert.match(modal, /confirmButtonText: "닫기"/);
  assert.match(modal, /settingsStore\.load\(/);
  assert.match(modal, /settingsStore\.change\(/);
  assert.match(modal, /settingsStore\.subscribe\(/);
});

test("모달: 닫힐 때 구독을 해제하고, 오류는 토스트가 아니라 모달 안에 보인다", () => {
  assert.match(modal, /willClose[\s\S]*?unsubscribe\(\)/);
  assert.doesNotMatch(modal, /toast\(/, "토스트를 띄우면 열린 모달이 닫힌다");
  assert.match(modal, /role: "alert"/);
});

test("홈: 설정은 공유 저장소에서 받고(실패해도 홈이 뜬다), 바뀌면 다시 그린다", () => {
  assert.match(home, /settingsStore\.load\(.*\)\.catch\(\(\) => null\)/);
  assert.match(home, /settingsStore\.subscribe\(/);
  assert.match(home, /startLabel\(settingsStore\.get\(\), mode\)/);
});

test("홈: 화면을 떠나면 구독을 해제한다", () => {
  assert.match(home, /unsubscribe\(\)/);
});

test("계정이 바뀔 때(로그아웃·탈퇴·세션 만료) 저장소를 비운다", () => {
  const resets = app.match(/settingsStore\.reset\(\)/g) ?? [];
  assert.ok(resets.length >= 3, `reset 호출이 ${resets.length}곳뿐이다`);
});

test("옛 상수(DAILY_GOAL, SESSION_SIZE, DEFAULT_COUNT)가 어디에도 남아 있지 않다", () => {
  const offenders = jsFiles(join(ROOT, "js")).filter((file) => /\b(DAILY_GOAL|SESSION_SIZE|DEFAULT_COUNT)\b/.test(readFileSync(file, "utf8")));
  assert.deepEqual(offenders, []);
});
