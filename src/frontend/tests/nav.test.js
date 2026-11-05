/*
 * 2026-11-05 - voda-voca - 하단 탭 내비게이션 규칙 테스트: 탭 정의, 활성 탭 판정, 탭바 표시 조건
 * 파일 위치: src/frontend/tests/nav.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { HOME_PATH, TABS, activeTabId, isTabbarVisible } from "../js/core/nav.js";

const USER = { id: 1, nickname: "tester" };

test("탭은 홈, 탐색, 복습함, 통계 4개이며 순서가 고정이다", () => {
  assert.deepEqual(
    TABS.map((tab) => [tab.id, tab.href, tab.label]),
    [
      ["home", "#/", "홈"],
      ["explore", "#/explore", "탐색"],
      ["review", "#/review", "복습함"],
      ["stats", "#/stats", "통계"],
    ],
  );
});

test("모든 탭에 아이콘 이름이 있다", () => {
  for (const tab of TABS) assert.ok(tab.iconName, tab.id);
});

test("홈 경로는 '/' 다", () => {
  assert.equal(HOME_PATH, "/");
});

test("activeTabId: 경로에 맞는 탭 id 를 돌려준다", () => {
  assert.equal(activeTabId("/"), "home");
  assert.equal(activeTabId("/explore"), "explore");
  assert.equal(activeTabId("/review"), "review");
  assert.equal(activeTabId("/stats"), "stats");
});

test("activeTabId: 하위 경로는 상위 탭으로 본다", () => {
  assert.equal(activeTabId("/explore/12"), "explore");
  assert.equal(activeTabId("/review/wrong"), "review");
});

test("activeTabId: 홈 탭은 '/' 정확히 일치할 때만 활성이다 (모든 경로의 접두사가 아니다)", () => {
  assert.equal(activeTabId("/exploreXYZ"), null);
  assert.equal(activeTabId("/unknown"), null);
  assert.equal(activeTabId("/study/session"), null);
  assert.equal(activeTabId(""), null);
});

test("isTabbarVisible: 로그인하지 않았으면 숨긴다", () => {
  assert.equal(isTabbarVisible("/", null), false);
  assert.equal(isTabbarVisible("/explore", undefined), false);
});

test("isTabbarVisible: 로그인·가입 화면에서는 숨긴다", () => {
  assert.equal(isTabbarVisible("/login", USER), false);
  assert.equal(isTabbarVisible("/signup", USER), false);
});

test("isTabbarVisible: 학습 세션 중에는 숨긴다 (한 문항에만 집중)", () => {
  assert.equal(isTabbarVisible("/study/session", USER), false);
  assert.equal(isTabbarVisible("/study/session/", USER), false);
});

test("isTabbarVisible: 탭 화면과 알 수 없는 경로에서는 보인다", () => {
  for (const path of ["/", "/explore", "/review", "/stats", "/nowhere"]) {
    assert.equal(isTabbarVisible(path, USER), true, path);
  }
});
