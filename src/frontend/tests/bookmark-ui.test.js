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
  assert.equal((session.match(/bookmarkFor\(item\)/g) ?? []).length, 3, "퀴즈 카드 1곳과 플래시카드 앞·뒷면 2곳에서 같은 헬퍼를 쓴다");
  assert.match(session, /bookmarks\.seed\(/);
  assert.match(session, /toast\([^)]*"error"/, "북마크 실패는 토스트로 알린다");
});

test("북마크 버튼 위치: 카드 오른쪽 위(.bookmark-slot), 카드가 기준 위치(relative)", () => {
  const css = read("css/app.css");
  assert.match(css, /\.bookmark-slot\s*\{[^}]*position:\s*absolute[^}]*top:[^}]*right:/s);
  assert.match(css, /\.session-card\s*\{[^}]*position:\s*relative/s);
  assert.match(css, /\.flip-face\s*\{[^}]*position:\s*absolute/s, "플래시카드는 각 면이 버튼의 기준 위치");
});

test("플래시카드: 북마크 버튼은 앞·뒷면 안에 각각 있어 카드와 함께 뒤집히고, 카드 밖에 따로 떠 있지 않다", () => {
  const session = read("js/views/study-session-view.js");
  const css = read("css/app.css");
  const fn = session.slice(session.indexOf("function renderFlashcard"), session.indexOf("function renderFlashcardButtons"));
  const front = fn.slice(fn.indexOf('{ class: "flip-face" }'), fn.indexOf('{ class: "flip-face flip-back" }'));
  const back = fn.slice(fn.indexOf('{ class: "flip-face flip-back" }'));
  assert.match(front, /bookmarkFor\(item\)/, "앞면 안");
  assert.match(back, /bookmarkFor\(item\)/, "뒷면 안");
  assert.doesNotMatch(fn, /flip-stage/, "카드 밖 형제 버튼(flip-stage)은 없앴다");
  assert.doesNotMatch(css, /\.flip-stage/);
});

test("플래시카드: 보이지 않는 면의 버튼은 탭 순서와 보조기기에서 뺀다 (앞면도 뒤집히면 inert)", () => {
  const session = read("js/views/study-session-view.js");
  assert.match(session, /querySelector\("\.flip-face:not\(\.flip-back\)"\)\.inert\s*=\s*flipped/, "뒤집기 동기화에서 앞면 inert");
  assert.match(session, /\.flip-back"\)\.inert\s*=\s*!\(flipped && !preview\)/, "뒷면 inert 는 기존대로");
  assert.match(session, /\.flip-face:not\(\.flip-back\)"\)\.inert\s*=\s*flipped && !preview/, "처음 그릴 때도 앞면 inert 를 맞춘다");
});

test("켜진 북마크는 hover 가 남아도 호박색을 유지한다 (터치 후 hover 고착 + .btn-ghost:hover 색 덮어쓰기 방지)", () => {
  const css = read("css/app.css");
  // .btn-ghost:hover:not(:disabled) 는 명시도 0,3,0 이라 같은 이상으로 맞서야 한다
  assert.match(css, /\.star-toggle\[aria-pressed="true"\]:hover:not\(:disabled\)\s*\{[^}]*color:\s*#f59e0b/s);
  // 터치 기기에서는 탭한 뒤 hover 배경이 남지 않게 한다
  assert.match(css, /@media \(hover:\s*none\)\s*\{[^}]*\.star-toggle:hover:not\(:disabled\)\s*\{[^}]*background:\s*var\(--btn-bg\)/s);
});
