/*
 * 2026-11-24 - voda-voca - 외부 CDN 의존 제거 검사: 화면 자원은 모두 vendor/ 에서 같은 출처로 제공한다 (Architecture A4 해소)
 * 파일 위치: src/frontend/tests/self-hosted.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const html = read("index.html");

/** 디렉터리를 재귀로 훑어 확장자가 맞는 파일 경로(ROOT 기준)를 모은다. vendor·tests 는 제외한다. */
function collect(dir, exts, out = []) {
  for (const name of readdirSync(join(ROOT, dir))) {
    const rel = join(dir, name);
    if (rel === "vendor" || rel === "tests" || name === "node_modules") continue;
    if (statSync(join(ROOT, rel)).isDirectory()) collect(rel, exts, out);
    else if (exts.some((e) => name.endsWith(e))) out.push(rel);
  }
  return out;
}

/** SVG 네임스페이스 선언(xmlns)은 네트워크 요청이 아니므로 허용한다. */
const stripAllowed = (text) => text.replaceAll("http://www.w3.org/", "");

test("앱 소스(index.html, css, js)에는 외부 http(s) URL 이 없다", () => {
  const files = ["index.html", ...collect("css", [".css"]), ...collect("js", [".js"])];
  assert.ok(files.length > 5, "검사 대상 파일을 찾았다");
  for (const file of files) {
    const hits = stripAllowed(read(file)).match(/https?:\/\/[^\s"')]+|\/\/(cdn|unpkg|fonts)\.[^\s"')]+/g) ?? [];
    assert.deepEqual(hits, [], `${file} 에 외부 URL 이 남아 있다`);
  }
});

test("index.html: 외부 자원 대신 vendor/ 경로를 버전과 함께 참조하고, 모두 실제 파일이다", () => {
  const refs = [...html.matchAll(/(?:href|src)="(vendor\/[^"]+)"/g)].map((m) => m[1]);
  for (const expected of [
    "vendor/tailwindcss-3.4.17.js",
    "vendor/sweetalert2-11.10.5/sweetalert2.min.css",
    "vendor/sweetalert2-11.10.5/sweetalert2.all.min.js",
    "vendor/lucide-0.460.0/lucide.min.js",
    "vendor/chart.js-4.6.2/chart.umd.js",
    "vendor/fonts/pretendard-1.3.9/pretendardvariable-dynamic-subset.css",
    "vendor/fonts/Paperlogy-7Bold.woff2",
  ]) {
    assert.ok(refs.includes(expected), `${expected} 를 참조한다`);
    assert.ok(existsSync(join(ROOT, expected)), `${expected} 파일이 있다`);
  }
});

test("Tailwind 스크립트는 tailwind.config 설정보다 먼저 로드한다", () => {
  assert.ok(html.indexOf("vendor/tailwindcss-3.4.17.js") !== -1);
  assert.ok(html.indexOf("vendor/tailwindcss-3.4.17.js") < html.indexOf("tailwind.config"));
});

test("Pretendard CSS 의 url() 은 모두 vendor 안에 실제로 있는 woff2 를 가리킨다", () => {
  const cssPath = "vendor/fonts/pretendard-1.3.9/pretendardvariable-dynamic-subset.css";
  const urls = [...read(cssPath).matchAll(/url\(([^)]+)\)/g)].map((m) => m[1].replace(/['"]/g, ""));
  assert.equal(urls.length, 92, "동적 서브셋 92개 조각을 모두 참조한다");
  for (const u of urls) {
    const abs = resolve(dirname(join(ROOT, cssPath)), u);
    assert.ok(abs.startsWith(join(ROOT, "vendor") + "/"), `${u} 는 vendor 밖을 가리키지 않는다`);
    assert.ok(existsSync(abs), `${relative(ROOT, abs)} 파일이 있다`);
  }
});

test("vendor/README.md 에 자원별 출처·버전·라이선스를 적어 둔다", () => {
  const doc = read("vendor/README.md");
  for (const name of ["Tailwind", "SweetAlert2", "Lucide", "Chart\\.js", "Pretendard", "Paperlogy"]) {
    assert.match(doc, new RegExp(name), `${name} 항목`);
  }
  assert.match(doc, /MIT/);
  assert.match(doc, /OFL/);
});
