/*
 * 2026-11-03 - voda-voca - 다크 모드 누락 방지 테스트: 화면 코드가 쓰는 색 클래스마다 다크 오버라이드가 있는지 검사한다 (이슈 #10)
 * 파일 위치: src/frontend/tests/dark-theme.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;

/** 밝은 화면과 어두운 화면 모두에서 그대로 읽히는 색. 다크 오버라이드가 필요 없다. */
const THEME_NEUTRAL = new Set([
  "text-white", // 인디고·빨강 버튼 위의 글자
  "hover:bg-indigo-700", // 주 버튼 hover: 더 짙은 인디고
  "hover:bg-red-700", // 위험 버튼 hover: 더 짙은 빨강
  "focus:border-indigo-500", // 입력 칸 포커스 테두리
  "focus:ring-indigo-500/15", // 입력 칸 포커스 링 (반투명)
]);

const COLOR_CLASS =
  /(?<![\w-])((?:[a-z-]+:)*(?:bg|text|border|ring|divide)-(?:green|emerald|red|amber|indigo|zinc|slate|white|black)(?:-\d+)?(?:\/\d+)?)/g;

/** @param {string} dir @returns {string[]} 하위 .js 파일 경로 */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

/** CSS 선택자에서 쓰는 형태로 이스케이프한다 (hover:bg-x/40 -> hover\:bg-x\/40). */
export function cssEscape(cls) {
  return cls.replace(/:/g, "\\:").replace(/\//g, "\\/");
}

/**
 * 사용 중인 색 클래스 중 다크 규칙이 없는 것을 찾는다.
 * @param {Iterable<string>} used
 * @param {string} css app.css 전체
 * @returns {string[]}
 */
export function missingDarkOverrides(used, css) {
  const start = css.indexOf("html.dark {");
  assert.ok(start >= 0, "app.css 에서 다크 테마 구간을 찾지 못했다");
  const dark = css.slice(start);
  return [...used].filter((cls) => !THEME_NEUTRAL.has(cls) && !dark.includes(`.${cssEscape(cls)}`)).sort();
}

test("missingDarkOverrides: 규칙이 없는 클래스를 잡아낸다 (검사기 자체 점검)", () => {
  const css = "html.dark { color-scheme: dark; }\nhtml.dark .bg-red-50 { background: red; }\nhtml.dark .hover\\:text-zinc-900:hover { color: #fff; }";
  assert.deepEqual(missingDarkOverrides(["bg-red-50", "bg-green-50", "hover:text-zinc-900", "hover:text-zinc-800"], css), [
    "bg-green-50",
    "hover:text-zinc-800",
  ]);
  assert.deepEqual(missingDarkOverrides(["text-white"], css), [], "테마 중립 색은 검사하지 않는다");
});

test("화면 코드가 쓰는 모든 색 클래스에는 다크 오버라이드가 있다", () => {
  const sources = [...jsFiles(join(ROOT, "js")), join(ROOT, "index.html")];
  const used = new Set();
  for (const file of sources) {
    for (const match of readFileSync(file, "utf8").matchAll(COLOR_CLASS)) used.add(match[1]);
  }
  assert.ok(used.size > 20, "색 클래스를 읽지 못했다. 검사 정규식을 확인하라");
  const css = readFileSync(join(ROOT, "css/app.css"), "utf8");
  assert.deepEqual(
    missingDarkOverrides(used, css),
    [],
    "다크 오버라이드가 없는 색 클래스가 있다. css/app.css 의 다크 구간에 규칙을 더하거나, 양쪽 테마에서 읽히는 색이면 THEME_NEUTRAL 에 올려라",
  );
});

// ---------- 공통 컴포넌트(.btn/.card/.chip) 다크 모드 누락 방지 (v2.2 4단계) ----------

/**
 * app.css 에서 `.btn*`, `.card*`, `.chip*` 규칙 중 색을 리터럴(#hex, rgb(), rgba())로 쓰는 것을 찾는다.
 * 컴포넌트는 var(--토큰) 만 써서 html.dark 의 토큰 교체로 다크가 따라오게 해야 한다.
 * 리터럴 색이 불가피하면 html.dark 에 같은 클래스 규칙을 두어야 한다.
 * @param {string} css app.css 전체
 * @returns {string[]} 다크 대응이 없는 선택자
 */
export function componentsWithoutDarkSupport(css) {
  const darkStart = css.indexOf("html.dark {");
  const dark = css.slice(darkStart);
  const bad = [];
  for (const m of css.matchAll(/(^|\n)((?:\.(?:btn|card|chip)[\w-]*[^{}\n]*,?\s*)+)\{([^}]*)\}/g)) {
    const selector = m[2].trim();
    const body = m[3].replace(/var\([^)]*\)/g, "");
    if (!/#[0-9a-fA-F]{3,8}\b|rgba?\(/.test(body)) continue;
    const firstClass = selector.match(/\.((?:btn|card|chip)[\w-]*)/)[1];
    if (!dark.includes(`html.dark .${firstClass}`)) bad.push(selector);
  }
  return bad;
}

test("componentsWithoutDarkSupport: 리터럴 색을 쓰면서 다크 규칙이 없는 컴포넌트를 잡아낸다 (검사기 자체 점검)", () => {
  const css = ".btn-x { background: #fff; }\n.btn-y { background: var(--surface); box-shadow: 0 3px 0 var(--e); }\n.chip-z { color: rgb(0,0,0); }\nhtml.dark {\n}\nhtml.dark .chip-z { color: #fff; }";
  assert.deepEqual(componentsWithoutDarkSupport(css), [".btn-x"]);
});

test(".btn/.card/.chip 컴포넌트는 리터럴 색 없이 토큰만 쓰거나, 쓰면 다크 규칙이 있다", () => {
  const css = readFileSync(join(ROOT, "css/app.css"), "utf8");
  assert.ok(/\n\.btn\s*\{/.test(css), "app.css 에서 .btn 컴포넌트를 찾지 못했다. 검사 정규식을 확인하라");
  assert.deepEqual(componentsWithoutDarkSupport(css), []);
});

test("다크 구간은 버튼 토큰(--btn-*, --on-accent)을 교체한다", () => {
  const css = readFileSync(join(ROOT, "css/app.css"), "utf8");
  const dark = css.slice(css.indexOf("html.dark {"));
  for (const token of ["--btn-primary-bg", "--btn-primary-edge", "--btn-danger-bg", "--btn-danger-edge", "--hover-bg"]) {
    assert.ok(dark.includes(token), `html.dark 에서 ${token} 을 정의해야 한다`);
  }
});
