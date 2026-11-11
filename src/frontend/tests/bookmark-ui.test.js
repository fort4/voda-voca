/*
 * 2026-11-10 - voda-voca - 세션 북마크 버튼 배치 검사: 퀴즈·플래시카드 카드의 오른쪽 위, 44px 터치 타깃, 카드 뒤집기 방지, 실패 토스트
 * 파일 위치: src/frontend/tests/bookmark-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("북마크 버튼: 44px 아이콘 버튼, aria-pressed, 카드 뒤집기 방지, 저장소 구독", () => {
  const src = read("js/views/components/bookmark-button.js");
  assert.match(src, /btn-icon/);
  assert.match(src, /star-toggle/);
  assert.match(src, /aria-pressed/);
  assert.match(src, /stopPropagation\(\)/, "플래시카드 위에서 눌러도 카드가 뒤집히지 않아야 한다");
  assert.match(src, /subscribe/);
  assert.match(src, /aria-label/);
});

test("세션 화면: 퀴즈 카드와 플래시카드 모두에 북마크 버튼을 두고, 실패하면 토스트로 알린다", () => {
  const session = read("js/views/study-session-view.js");
  assert.match(session, /createBookmarkStore\(/);
  assert.match(session, /bookmarkButton\(/);
  assert.equal((session.match(/bookmarkFor\(item\)/g) ?? []).length, 2, "퀴즈 카드와 플래시카드, 두 곳에서 같은 헬퍼를 쓴다");
  assert.match(session, /bookmarks\.seed\(/);
  assert.match(session, /toast\([^)]*"error"/, "북마크 실패는 토스트로 알린다");
});

test("북마크 버튼 위치: 카드 오른쪽 위(.bookmark-slot), 카드가 기준 위치(relative)", () => {
  const css = read("css/app.css");
  assert.match(css, /\.bookmark-slot\s*\{[^}]*position:\s*absolute[^}]*top:[^}]*right:/s);
  assert.match(css, /\.session-card\s*\{[^}]*position:\s*relative/s);
  assert.match(css, /\.flip-stage\s*\{[^}]*position:\s*relative/s);
});

test("켜진 북마크는 hover 가 남아도 호박색을 유지한다 (터치 후 hover 고착 + .btn-ghost:hover 색 덮어쓰기 방지)", () => {
  const css = read("css/app.css");
  // .btn-ghost:hover:not(:disabled) 는 명시도 0,3,0 이라 같은 이상으로 맞서야 한다
  assert.match(css, /\.star-toggle\[aria-pressed="true"\]:hover:not\(:disabled\)\s*\{[^}]*color:\s*#f59e0b/s);
  // 터치 기기에서는 탭한 뒤 hover 배경이 남지 않게 한다
  assert.match(css, /@media \(hover:\s*none\)\s*\{[^}]*\.star-toggle:hover:not\(:disabled\)\s*\{[^}]*background:\s*var\(--btn-bg\)/s);
});
