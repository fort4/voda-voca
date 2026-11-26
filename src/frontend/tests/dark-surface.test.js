/*
 * 2026-11-26 - voda-voca - 다크 모드 표면 계층 검사: 배경 < 카드 < 컨트롤 < 트랙 명도, 반투명 테두리, 버튼 위계, 보조 글자 대비
 * 파일 위치: src/frontend/tests/dark-surface.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const css = readFileSync(join(ROOT, "css/app.css"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
  selectors: m[1].split(",").map((s) => s.trim()),
  body: m[2],
  at: m.index,
}));

/** @returns {string} 선택자 목록에 selector 가 정확히 들어 있는 규칙들의 선언 */
const declarations = (selector) => rules.filter((r) => r.selectors.includes(selector)).map((r) => r.body).join(";");

/** @returns {string} 해당 블록(:root 또는 html.dark)에서 마지막으로 선언한 토큰 값 */
function token(scope, name) {
  const found = [...declarations(scope).matchAll(new RegExp(`(?:^|[;\\s])${name}\\s*:\\s*([^;]+)`, "g"))];
  assert.ok(found.length, `${scope} 에 ${name} 이 없다`);
  return found.at(-1)[1].trim();
}

function luminance(hex) {
  assert.match(hex, /^#[0-9a-f]{6}$/i, `6자리 hex 가 아니다: ${hex}`);
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
/** @returns {number} 반투명 흰색 rgba(255,255,255,a) 의 a */
function whiteAlpha(value) {
  const m = value.match(/^rgba\(255,\s*255,\s*255,\s*([\d.]+)\)$/);
  assert.ok(m, `반투명 흰색이 아니다: ${value}`);
  return Number(m[1]);
}

const dark = (name) => token("html.dark", name);

test("표면 계층: 페이지 #0f1115, 카드 #181b22, 카드 안 컨트롤 #222630", () => {
  assert.equal(dark("--bg"), "#0f1115");
  assert.equal(dark("--surface"), "#181b22");
  assert.equal(dark("--control"), "#222630");
});

test("명도는 페이지 < 카드 < 컨트롤 < 호버·트랙 순으로 밝아진다", () => {
  const [bg, surface, control] = ["--bg", "--surface", "--control"].map((n) => luminance(dark(n)));
  assert.ok(bg < surface && surface < control);
  assert.ok(luminance(dark("--hover-bg")) > control, "호버가 컨트롤보다 어두우면 눌리는 느낌이 거꾸로 된다");
  assert.ok(contrast(dark("--track"), dark("--surface")) >= 1.35, "빈 트랙이 카드 배경과 구분되지 않는다");
  assert.ok(contrast(dark("--accent"), dark("--track")) >= 3, "채움과 빈 트랙이 구분되지 않는다");
});

test("테두리는 반투명 흰색 0.10~0.16, 주요 버튼 테두리는 0.22", () => {
  assert.equal(whiteAlpha(dark("--border")), 0.1);
  assert.equal(whiteAlpha(dark("--border-strong")), 0.16);
  assert.equal(whiteAlpha(dark("--btn-cta-border")), 0.22);
  assert.ok(whiteAlpha(dark("--btn-cta-border-hover")) > 0.22, "호버에서 테두리가 어두워지면 안 된다");
});

test("보조 글자는 #a1a7b5 보다 밝고 모든 표면에서 4.5:1 이상이다", () => {
  assert.ok(luminance(dark("--muted")) > luminance("#a1a7b5"));
  for (const bg of ["--bg", "--surface", "--control"]) {
    assert.ok(contrast(dark("--muted"), dark(bg)) >= 4.5, `${bg} 대비 부족`);
  }
});

test("메타 정보에 쓰는 text-zinc-500 은 다크에서 --muted 를 따른다", () => {
  assert.match(declarations("html.dark .text-zinc-500"), /color:\s*var\(--muted\)/);
});

test("비활성 필터 칩과 보조 버튼은 --control 배경을 쓴다", () => {
  assert.match(declarations(".chip"), /background:\s*var\(--control\)/);
  assert.match(declarations(".btn-secondary"), /--btn-bg:\s*var\(--control\)/);
  assert.match(declarations(".count-choice"), /background:\s*var\(--control\)/);
});

test("진행 막대 트랙은 모두 --track 을 쓴다", () => {
  const tracks = rules.filter((r) => r.selectors.includes(".progress-track"));
  assert.ok(tracks.length > 0);
  for (const r of tracks) assert.match(r.body, /background:\s*var\(--track\)/);
});

test("단어장 카드: 미리보기는 투명 + 테두리, 학습 버튼은 밝은 테두리이며 공통 규칙보다 뒤에 있다", () => {
  const preview = declarations(".vocab-card .btn-ghost");
  assert.match(preview, /border-color:\s*var\(--btn-outline-border\)/);
  assert.equal(dark("--btn-outline-border"), "var(--border-strong)");
  assert.match(declarations(".btn-ghost"), /--btn-bg:\s*transparent/);
  assert.match(declarations(".vocab-card .btn-secondary"), /border-color:\s*var\(--btn-cta-border\)/);
  assert.match(declarations(".vocab-card .btn-secondary:hover:not(:disabled)"), /border-color:\s*var\(--btn-cta-border-hover\)/);
  const position = (selector) => rules.find((r) => r.selectors.includes(selector)).at;
  assert.ok(position(".vocab-card .btn-secondary") > position(".vocab-card .btn"));
  assert.ok(position(".vocab-card .btn-secondary:hover:not(:disabled)") > position(".vocab-card .btn:hover:not(:disabled)"));
});

test("라이트 모드의 새 토큰은 기존 색을 그대로 가리킨다", () => {
  assert.equal(token(":root", "--control"), "#ffffff");
  assert.equal(token(":root", "--track"), "var(--border)");
  assert.equal(token(":root", "--btn-outline-border"), "var(--border)");
  assert.equal(token(":root", "--btn-cta-border"), "var(--border)");
  assert.equal(token(":root", "--btn-cta-border-hover"), "var(--border-strong)");
});

test("다크 규칙에 이전 zinc 표면색이 남아 있지 않다 (표면은 토큰을 따른다)", () => {
  const old = /#09090b|#18181b|#27272a|#3f3f46|rgba\(9,\s*9,\s*11|rgba\(24,\s*24,\s*27/i;
  const offenders = rules
    .filter((r) => r.selectors.some((s) => s.startsWith("html.dark")) && old.test(r.body))
    .map((r) => r.selectors.join(", "));
  assert.deepEqual(offenders, []);
});
