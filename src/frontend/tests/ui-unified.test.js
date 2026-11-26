/*
 * 2026-11-26 - voda-voca - 화면 공통 시각 규칙 검사: 진행 막대 하나의 모양과 의미 색, 세그먼트 선택 표시, 카드 제목, 홈·탐색·복습함·마이페이지·학습 결과의 통일
 * 파일 위치: src/frontend/tests/ui-unified.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (rel) => readFileSync(new URL(`../${rel}`, import.meta.url), "utf8");
const css = read("css/app.css").replace(/\/\*[\s\S]*?\*\//g, "");
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({ selectors: m[1].split(",").map((s) => s.trim()), body: m[2], at: m.index }));
const declarations = (selector) => rules.filter((r) => r.selectors.includes(selector)).map((r) => r.body).join(";");

test("진행 막대의 기본 규칙은 하나이고, 채움은 의미 색 변수의 그라데이션이다", () => {
  for (const selector of [".progress-track", ".progress-fill"]) {
    assert.equal(rules.filter((r) => r.selectors.includes(selector) && /height|background/.test(r.body)).length, 1, `${selector} 규칙이 여러 개면 화면마다 모양이 달라진다`);
  }
  assert.match(declarations(".progress-track"), /height:\s*10px/);
  assert.match(declarations(".progress-fill"), /linear-gradient\(90deg,\s*var\(--meter-from\),\s*var\(--meter-to\)\)/);
  assert.match(declarations(".session-header .progress-track"), /flex:\s*1/);
});

test("막대 색은 의미별(학습·목표·달성·오답)이며 두 테마에 모두 정의한다", () => {
  const base = rules.find((r) => r.selectors.includes(".progress-track")).at;
  for (const tone of ["goal", "ok", "wrong"]) {
    const rule = rules.find((r) => r.selectors.includes(`.meter--${tone}`));
    assert.ok(rule, `.meter--${tone} 이 없다`);
    assert.match(rule.body, new RegExp(`--meter-from:\\s*var\\(--meter-${tone}-from\\)`));
    assert.ok(rule.at > base, "기본 색보다 뒤에 있어야 덮어쓴다");
  }
  for (const scope of [":root", "html.dark"]) {
    for (const tone of ["progress", "goal", "ok", "wrong"]) {
      for (const end of ["from", "to"]) assert.match(declarations(scope), new RegExp(`--meter-${tone}-${end}:`), `${scope} --meter-${tone}-${end}`);
    }
  }
});

test("홈과 탐색의 진행 막대는 퍼센트를 함께 보여 준다", () => {
  assert.match(read("js/views/components/progress-bar.js"), /export function progressRow\(/);
  assert.match(read("js/views/home-view.js"), /progressRow\(m\.progressPercent/);
  assert.match(read("js/views/home-view.js"), /progressRow\(m\.goalPercent[^)]*"ok"\s*:\s*"goal"\)/);
  assert.match(read("js/views/explore-view.js"), /progressRow\(c\.progressPercent/);
});

test("세그먼트(학습 방식, 출제 설정, 복습함 탭)는 같은 모양이고 선택 칸을 강조색으로 표시한다", () => {
  for (const file of ["js/views/components/mode-toggle.js", "js/views/components/quiz-options.js", "js/views/review-view.js"]) {
    const src = read(file);
    assert.match(src, /"segmented[ "]/, `${file} 바탕`);
    assert.match(src, /segment press focus-ring/, `${file} 칸`);
    assert.doesNotMatch(src, /bg-white|bg-zinc-100/, `${file} 에 이전 색 클래스가 남아 있다`);
  }
  for (const selector of ['.segment[aria-pressed="true"]', '.segment[aria-selected="true"]']) {
    assert.match(declarations(selector), /background:\s*var\(--accent-soft\)/);
    assert.match(declarations(selector), /box-shadow:\s*inset 0 0 0 1\.5px var\(--accent\)/);
  }
});

test("카드 제목은 공통 부품(색 아이콘 + 제목)을 쓴다", () => {
  const component = read("js/views/components/card-heading.js");
  assert.match(component, /export function iconBadge\(/);
  assert.match(component, /export function cardHeading\(/);
  for (const view of ["home", "review", "mypage", "stats"]) {
    assert.match(read(`js/views/${view}-view.js`), /components\/card-heading\.js/, `${view} 화면`);
  }
  assert.match(declarations(".icon-badge"), /var\(--tone/);
  for (const tone of ["accent", "activity", "words", "wrong", "ok"]) assert.match(declarations(`.tone-${tone}`), /--tone:/, tone);
});

test("카드와 지표 칸의 배경은 의미 색을 쓰지 않는 한 가지 표면색이다 (색은 아이콘·막대에만)", () => {
  assert.doesNotMatch(css, /card-tinted/);
  for (const view of ["home", "explore", "review", "mypage", "stats"]) {
    assert.doesNotMatch(read(`js/views/${view}-view.js`), /card-tinted/, `${view} 화면`);
  }
  assert.match(declarations(".stat-cell"), /background:\s*var\(--surface\)/);
  for (const selector of [".avatar-badge", ".trophy-badge"]) {
    assert.doesNotMatch(declarations(selector), /gradient/, selector);
  }
});

test("연속 학습일은 이모지가 아니라 아이콘 알약으로 보인다", () => {
  const home = read("js/views/home-view.js");
  assert.doesNotMatch(home, /🔥/);
  assert.match(home, /icon\("flame"/);
});

test("탐색: 학습 중인 카드는 테두리로 구분하고, 긴 버튼 글자가 접히지 않게 폭을 더 준다", () => {
  const view = read("js/views/explore-view.js");
  assert.match(view, /vocab-card--active/);
  assert.match(view, /vocab-actions/);
  assert.match(declarations(".vocab-card.vocab-card--active"), /border-color:\s*var\(--accent\)/);
  assert.match(declarations(".vocab-actions"), /grid-template-columns:\s*minmax\(0,\s*2fr\)\s+minmax\(0,\s*3fr\)/);
});

test("복습함 목록은 출처에 따라 색 띠를 두른다", () => {
  assert.match(read("js/views/review-view.js"), /word-row/);
  assert.match(declarations(".word-row"), /border-left:\s*3px solid var\(--tone/);
});

test("학습 결과의 지표 칸은 지표마다 아이콘과 색을 가진다", () => {
  const view = read("js/views/components/session-result.js");
  for (const label of ["정답률", "맞힌 문제", "최대 콤보", "새로 숙련"]) assert.match(view, new RegExp(`"?${label}"?:`), label);
  assert.match(view, /iconBadge\(/);
});
