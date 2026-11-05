/*
 * 2026-11-05 - voda-voca - 라우트 표 테스트: 신규 학습 중심 라우트, 접근 권한, 폐기된 라우트
 * 파일 위치: src/frontend/tests/routes.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { matchRoute } from "../js/core/router.js";
import { buildRoutes } from "../js/routes.js";

const NAMES = ["login", "signup", "home", "explore", "session", "review", "stats"];
const views = Object.fromEntries(NAMES.map((name) => [name, () => name]));
const routes = buildRoutes(views);

function hit(path) {
  const match = matchRoute(routes, path);
  return match ? { view: match.route.view(), access: match.route.access } : null;
}

test("학습 중심 라우트가 모두 등록되어 있고 로그인이 필요하다", () => {
  assert.deepEqual(hit("/"), { view: "home", access: "user" });
  assert.deepEqual(hit("/explore"), { view: "explore", access: "user" });
  assert.deepEqual(hit("/study/session"), { view: "session", access: "user" });
  assert.deepEqual(hit("/review"), { view: "review", access: "user" });
  assert.deepEqual(hit("/stats"), { view: "stats", access: "user" });
});

test("로그인·가입은 비로그인 전용이다", () => {
  assert.deepEqual(hit("/login"), { view: "login", access: "guest" });
  assert.deepEqual(hit("/signup"), { view: "signup", access: "guest" });
});

test("폐기된 관리형 라우트는 더 이상 연결되지 않는다", () => {
  for (const path of [
    "/wordbooks",
    "/wordbooks/3",
    "/study/flashcards",
    "/study/quiz",
    "/bookmarks",
    "/history",
  ]) {
    assert.equal(hit(path), null, path);
  }
});

test("패턴이 겹치지 않는다", () => {
  const patterns = routes.map((route) => route.pattern);
  assert.equal(new Set(patterns).size, patterns.length);
});

test("모든 라우트는 올바른 권한 값을 가진다", () => {
  for (const route of routes) assert.ok(["any", "user", "guest"].includes(route.access), route.pattern);
});

test("필요한 화면이 빠지면 바로 알 수 있다", () => {
  assert.throws(() => buildRoutes({ ...views, explore: undefined }), /explore/);
});
