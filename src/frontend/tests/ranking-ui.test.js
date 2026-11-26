/*
 * 2026-11-26 - voda-voca - 학습 순위 배선 검사: 라우트와 탭, 통계 안 전환, 순위 화면, 마이페이지 공개 스위치, 선택 표시 스타일 (REQ-172, REQ-173)
 * 파일 위치: src/frontend/tests/ranking-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import { activeTabId, isTabbarVisible } from "../js/core/nav.js";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");
const css = read("css/app.css").replace(/\/\*[\s\S]*?\*\//g, "");
const declarations = (selector) =>
  [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter((m) => m[1].split(",").some((s) => s.trim() === selector))
    .map((m) => m[2])
    .join(";");

test("순위 화면은 통계 탭에 속하고 탭바가 보인다", () => {
  assert.equal(activeTabId("/stats/ranking"), "stats");
  assert.equal(isTabbarVisible("/stats/ranking", { id: 1 }), true);
  assert.match(read("js/app.js"), /ranking:\s*rankingView/);
});

test("전환: '내 통계'와 '순위' 링크이며 지금 화면을 aria-current 로 알린다", () => {
  const src = read("js/views/components/stats-switch.js");
  assert.match(src, /"#\/stats"[\s\S]*"내 통계"/);
  assert.match(src, /"#\/stats\/ranking"[\s\S]*"순위"/);
  assert.match(src, /"aria-current":/);
  assert.match(src, /"segmented[ "]/);
});

test("통계 화면: 전환은 로더 밖에 있어 기록이 없거나 불러오는 중에도 보인다", () => {
  const src = read("js/views/stats-view.js");
  assert.match(src, /root\.append\(statsSwitch\("stats"\), body\)/);
  assert.match(src, /mountLoader\(body,/);
});

test("순위 화면: 조회 API 만 쓰고, 지표를 고르며, 본인 줄은 색 말고 글자로도 표시한다", () => {
  const src = read("js/views/ranking-view.js");
  assert.match(src, /statsSwitch\("ranking"\)/);
  assert.match(src, /api\("\/ranking",\s*\{\s*query:\s*\{\s*metric/);
  assert.doesNotMatch(src, /method:/, "다른 사람의 기록을 바꾸는 호출이 없다 (VOCA-FR-053)");
  assert.match(src, /RANKING_METRICS/);
  assert.match(src, /"aria-pressed"/);
  assert.match(src, /ranking-row--me/);
  assert.match(src, /"나"/);
  assert.match(src, /navigate\("\/mypage"\)/);
  assert.doesNotMatch(src, /innerHTML/);
});

test("마이페이지: 공개 스위치와 안내, 순위 화면 링크", () => {
  const src = read("js/views/mypage-view.js");
  assert.match(src, /createRankingVisibility\(/);
  assert.match(src, /role:\s*"switch"/);
  assert.match(src, /"aria-checked"/);
  assert.match(src, /RANKING_VISIBILITY_NOTE/);
  assert.match(src, /"#\/stats\/ranking"/);
  assert.match(read("js/core/ranking-model.js"), /닉네임과 학습 지표가 다른 사용자에게 보여요\. 단어장과 단어는 보이지 않아요\./);
});

test("스타일: 전환의 선택 칸은 세그먼트 표시를 따르고, 순위 강조는 강조색 테두리·배지다", () => {
  assert.match(declarations('.segment[aria-current="page"]'), /box-shadow:\s*inset 0 0 0 1\.5px var\(--accent\)/);
  assert.match(declarations(".rank-badge--lead"), /color:\s*var\(--accent\)/);
  assert.match(declarations(".ranking-row--me"), /border-color:\s*var\(--accent\)/);
  assert.doesNotMatch(declarations(".ranking-row--me"), /background/);
});
