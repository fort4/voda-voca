/*
 * 2026-11-10 - voda-voca - 학습 개수 설정 UI 배선 테스트: 설정 API 연동, 낙관적 갱신·롤백, 옵션 하드코딩 금지, 터치 크기, 옛 상수 제거 (REQ-147)
 * 파일 위치: src/frontend/tests/settings-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const card = read("js/views/components/settings-card.js");
const home = read("js/views/home-view.js");

/** @param {string} dir @returns {string[]} */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

test("설정 카드: 칩은 서버가 준 옵션으로 만들고 10/20/30 을 직접 적지 않는다", () => {
  assert.match(card, /settings\.options\.map/);
  const code = card.replace(/\/\*[\s\S]*?\*\//g, ""); // 주석은 제외하고 코드만 본다
  assert.doesNotMatch(code, /\b(10|20|30)\b/);
});

test("설정 카드: 칩은 기존 .chip 컴포넌트에 aria-pressed 로 선택을 나타내고 터치 높이 44px 이상", () => {
  assert.match(card, /class: "chip [^"]*min-h-\[44px\]/);
  assert.match(card, /"aria-pressed"/);
});

test("설정 카드: 세 행은 퀴즈·플래시카드·오늘의 목표 모델 정의를 그대로 쓴다", () => {
  assert.match(card, /SETTING_ROWS\.map/);
});

test("홈: 설정을 GET 으로 받고, 실패해도 홈이 뜨도록 catch 후 정규화한다", () => {
  assert.match(home, /api\("\/users\/me\/settings"\)\.catch\(\(\) => null\)/);
  assert.match(home, /normalizeSettings\(settings\)/);
});

test("홈: 선택 즉시 반영하고 PATCH 로 저장하며, 실패하면 이전 값으로 되돌리고 토스트를 띄운다", () => {
  assert.match(home, /method: "PATCH", body: \{ \[key\]: value \}/);
  assert.match(home, /applySetting\(settings, key, previous\)/);
  assert.match(home, /toast\("설정을 저장하지 못했어요", "error"\)/);
});

test("홈: 시작 버튼 문구와 목표는 설정에서 오고, 모드를 바꾸면 다시 그린다", () => {
  assert.match(home, /startLabel\(data\.settings, mode\)/);
  assert.match(home, /function setMode\(next\)[\s\S]*?repaint\(\)/);
});

test("옛 상수(DAILY_GOAL, SESSION_SIZE, DEFAULT_COUNT)가 어디에도 남아 있지 않다", () => {
  const offenders = jsFiles(join(ROOT, "js")).filter((file) => /\b(DAILY_GOAL|SESSION_SIZE|DEFAULT_COUNT)\b/.test(readFileSync(file, "utf8")));
  assert.deepEqual(offenders, []);
});
