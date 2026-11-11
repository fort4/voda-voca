/*
 * 2026-11-11 - voda-voca - 제목·큰 글씨 전용 폰트(Paperlogy) 테스트: 버전 고정, 폴백, 적용 범위 (본문·발음기호는 Pretendard 유지)
 * 파일 위치: src/frontend/tests/display-font.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const css = read("css/app.css");
const html = read("index.html");

test("@font-face: Paperlogy 를 버전 고정(@latest 금지) woff2 로 불러오고 font-display: swap 을 쓴다", () => {
  const face = css.match(/@font-face\s*\{[^}]*Paperlogy[^}]*\}/)?.[0];
  assert.ok(face, "Paperlogy @font-face 가 있다");
  assert.match(face, /Paperlogy-7Bold\.woff2/);
  assert.match(face, /2408-3@1\.0\//);
  assert.doesNotMatch(face, /@latest/);
  assert.match(face, /font-display:\s*swap/);
  assert.match(face, /font-weight:\s*600 800/, "제목(700)·학습 단어(800) 모두 합성 굵기 없이 이 파일로 그린다");
});

test("--font-display 토큰은 Paperlogy 가 실패하면 본문 폰트 체인으로 돌아간다", () => {
  assert.match(css, /--font-display:\s*"Paperlogy",\s*var\(--font-sans\)/);
});

test("제목·화면 제목·학습 단어·브랜드명에만 display 폰트를 적용한다", () => {
  const rule = css.match(/([^{}]*)\{[^}]*font-family:\s*var\(--font-display\)[^}]*\}/)?.[1] ?? "";
  for (const sel of [".text-heading", ".text-title", ".text-display", ".session-term", ".brand-name"]) {
    assert.ok(rule.includes(sel), `${sel} 에 적용`);
  }
  assert.doesNotMatch(rule, /\bbody\b/, "본문은 Pretendard 그대로");
});

test("본문·발음기호는 계속 Pretendard 체인을 쓴다", () => {
  assert.match(css, /body\s*\{[^}]*font-family:\s*var\(--font-sans\)/);
  assert.match(css, /--font-ipa:\s*var\(--font-sans\)/);
  assert.match(css, /\.phonetic\s*\{[^}]*font-family:\s*var\(--font-ipa\)/);
});

test("index.html: 폰트 파일을 미리 요청하고 브랜드명에 brand-name 클래스를 단다", () => {
  assert.match(html, /<link rel="preload" as="font" type="font\/woff2" crossorigin href="[^"]*Paperlogy-7Bold\.woff2"/);
  assert.match(html, /class="brand-name[^"]*"[^>]*>보다보카/);
});
