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
