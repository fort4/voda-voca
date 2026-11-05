/*
 * 2026-11-05 - voda-voca - 디자인 토큰·폰트 도입 검사: 타입/간격/반경 토큰, Pretendard 로딩, Tailwind 타입 스케일 등록 (v2.2 DS-1, DS-2)
 * 파일 위치: src/frontend/tests/design-tokens.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname;
const css = readFileSync(`${ROOT}css/app.css`, "utf8");
const html = readFileSync(`${ROOT}index.html`, "utf8");

/** app.css 의 첫 `:root { ... }` 블록 중 토큰 선언 전체를 이어 붙여 돌려준다. */
function rootBlocks() {
  return [...css.matchAll(/:root\s*\{([^}]*)\}/g)].map((m) => m[1]).join("\n");
}

const TOKENS = [
  "--font-sans",
  "--fs-micro", "--fs-caption", "--fs-body", "--fs-lead", "--fs-heading", "--fs-title", "--fs-display",
  "--lh-tight", "--lh-normal", "--lh-relaxed",
  "--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6", "--space-8",
  "--radius-sm", "--radius-control", "--radius-card", "--radius-pill",
];

for (const token of TOKENS) {
  test(`:root 에 ${token} 토큰이 정의되어 있다`, () => {
    assert.match(rootBlocks(), new RegExp(`${token}\\s*:`));
  });
}

test("--font-sans 는 Pretendard Variable 로 시작하고 시스템 폰트로 폴백한다", () => {
  const m = rootBlocks().match(/--font-sans\s*:\s*([^;]+);/);
  assert.ok(m, "--font-sans 선언이 없다");
  assert.match(m[1], /^\s*["']?Pretendard Variable["']?/);
  for (const fallback of ["Pretendard", "-apple-system", "system-ui", "sans-serif"]) {
    assert.ok(m[1].includes(fallback), `폴백 체인에 ${fallback} 이(가) 없다`);
  }
});

test("body 는 --font-sans 를 쓰고 한글 단어 단위 줄바꿈을 한다", () => {
  const body = css.match(/\n\}\nbody\s*\{([^}]*)\}/)?.[1] ?? ""; // `html,\nbody {` 공용 블록이 아닌 단독 body 규칙
  assert.match(body, /font-family:\s*var\(--font-sans\)/);
  assert.match(body, /word-break:\s*keep-all/);
});

test("index.html: Pretendard Variable 을 preconnect 와 함께 CDN 에서 불러온다 (swap 서브셋 CSS)", () => {
  assert.match(html, /<link[^>]+rel="preconnect"[^>]+href="https:\/\/cdn\.jsdelivr\.net"/);
  assert.match(html, /<link[^>]+rel="stylesheet"[^>]+pretendard[^>]*variable[^>]*dynamic-subset[^>]*\.css/i);
});

test("index.html: Tailwind 설정에 fontFamily 와 타입 스케일(fontSize)이 등록되어 있다", () => {
  const cfg = html.match(/tailwind\.config\s*=\s*(\{[\s\S]*?\n\s{6}\});/)?.[1] ?? "";
  assert.ok(cfg, "tailwind.config 블록을 찾지 못했다");
  assert.match(cfg, /fontFamily/);
  assert.match(cfg, /var\(--font-sans\)/);
  for (const step of ["micro", "caption", "body", "lead", "heading", "title", "display"]) {
    assert.match(cfg, new RegExp(`\\b${step}\\b`), `fontSize 에 ${step} 단계가 없다`);
  }
});

test("Tailwind 설정 스크립트는 Play CDN 스크립트보다 뒤에 온다", () => {
  assert.ok(html.indexOf("cdn.tailwindcss.com") < html.indexOf("tailwind.config"));
});
