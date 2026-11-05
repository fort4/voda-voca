/*
 * 2026-11-02 - voda-voca - 라우터 순수 함수 테스트: 해시 파싱, 패턴 매칭, next 경로 검사 (열린 리다이렉트 방지)
 * 파일 위치: src/frontend/tests/router.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { matchRoute, parseHash, safeNext } from "../js/core/router.js";

test("parseHash: 빈 해시는 루트, 쿼리는 객체로 바꾼다", () => {
  assert.deepEqual(parseHash(""), { path: "/", query: {} });
  assert.deepEqual(parseHash("#/login?next=%2Fwordbooks"), { path: "/login", query: { next: "/wordbooks" } });
});

test("parseHash: 끝의 슬래시는 제거하고 앞 슬래시가 없어도 맞춘다", () => {
  assert.equal(parseHash("#/wordbooks/").path, "/wordbooks");
  assert.equal(parseHash("#wordbooks").path, "/wordbooks");
});

test("matchRoute: 패턴의 :name 을 params 로 받고, 리터럴이 다르면 null", () => {
  const routes = [
    { pattern: "/login", access: "guest", view: 1 },
    { pattern: "/wordbooks/:id", access: "user", view: 2 },
  ];
  const hit = matchRoute(routes, "/wordbooks/42");
  assert.equal(hit.route.view, 2);
  assert.deepEqual(hit.params, { id: "42" });
  assert.equal(matchRoute(routes, "/wordbooks"), null);
  assert.equal(matchRoute(routes, "/nope"), null);
});

test("matchRoute: 루트 패턴은 루트 경로에만 맞는다", () => {
  const routes = [{ pattern: "/", access: "any", view: "root" }];
  assert.equal(matchRoute(routes, "/").route.view, "root");
  assert.equal(matchRoute(routes, "/x"), null);
});

test("safeNext: 같은 앱의 경로만 허용하고 나머지는 기본값으로 바꾼다", () => {
  assert.equal(safeNext("/explore/3?x=1"), "/explore/3?x=1");
  assert.equal(safeNext("https://evil.example/"), "/");
  assert.equal(safeNext("//evil.example"), "/");
  assert.equal(safeNext("javascript:alert(1)"), "/");
  assert.equal(safeNext(undefined), "/");
  assert.equal(safeNext("/a b", "/home"), "/home");
});
