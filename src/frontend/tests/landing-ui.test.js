/*
 * 2026-11-26 - voda-voca - 메인 소개(Landing) 화면 테스트: 비로그인 시 #/ 에서 서비스 소개·단어장 카탈로그·핵심 기능·가입/로그인 CTA 를 보여 준다
 * 파일 위치: src/frontend/tests/landing-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { createRouter } from "../js/core/router.js";
import { buildRoutes } from "../js/routes.js";
import { LANDING_FEATURES, LANDING_VOCABULARIES } from "../js/views/landing-view.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");

test("LANDING_VOCABULARIES: 초등·중고등·수능·시험·비즈니스 5종 기본 단어장을 간결히 보여 준다", () => {
  assert.equal(LANDING_VOCABULARIES.length, 5);
  const categories = LANDING_VOCABULARIES.map((v) => v.category);
  for (const label of ["초등", "중고등", "수능", "시험", "비즈니스"]) {
    assert.ok(categories.includes(label), `${label} 단어장 포함`);
  }
  for (const vocab of LANDING_VOCABULARIES) {
    assert.ok(vocab.title && vocab.words, `${vocab.title} 항목 값 확인`);
  }
});

test("LANDING_FEATURES: 핵심 기능 3가지(퀴즈/플래시카드, 복습함, 나만의 단어장·통계)만 간결하게 요약한다", () => {
  assert.equal(LANDING_FEATURES.length, 3);
  const text = LANDING_FEATURES.map((f) => `${f.title} ${f.description}`).join(" ");
  for (const keyword of ["퀴즈", "플래시카드", "복습", "단어장", "CSV", "통계"]) {
    assert.ok(text.includes(keyword), `핵심 기능 키워드 누락: ${keyword}`);
  }
});

test("LANDING_VOCABULARIES: 이름·순서·단어 수가 실제 표준 단어장 시드와 같다", () => {
  const seeds = "../backend/data/seeds";
  const catalog = JSON.parse(read(`${seeds}/vocabularies.json`)).toSorted((a, b) => a.sort_order - b.sort_order);
  assert.deepEqual(
    LANDING_VOCABULARIES.map((v) => v.title),
    catalog.map((v) => v.title.replace(/( 영단어)? 200$/, "")),
  );
  assert.deepEqual(
    LANDING_VOCABULARIES.map((v) => v.words),
    catalog.map((v) => `${JSON.parse(read(`${seeds}/words/${v.slug}.json`)).length}단어`),
  );
});

test("LANDING_FEATURES: 브라우저 음성 합성을 원어민 발음이라고 부르지 않는다", () => {
  const text = LANDING_FEATURES.map((f) => f.description).join(" ");
  assert.doesNotMatch(text, /원어민/);
  assert.match(text, /영어 발음 듣기\(TTS\)/);
});

test("landing-view.js: 로그인·회원가입 이동 버튼과 히어로·단어장·기능 섹션을 그리며 디자인 시스템(.card, brandLogo)을 따른다", () => {
  const src = read("js/views/landing-view.js");
  assert.match(src, /brandLogo\(/);
  assert.match(src, /"\/signup"/);
  assert.match(src, /"\/login"/);
  assert.match(src, /\bcard\b/);
  assert.doesNotMatch(src, /innerHTML/);
});

test("라우팅: 비로그인 사용자가 #/ 로 접속하면 로그인 화면으로 쫓겨나지 않고 메인 소개 화면을 본다", () => {
  const calls = [];
  let currentUser = null;
  const views = {
    landing: () => calls.push("landing"),
    home: () => calls.push("home"),
    login: () => calls.push("login"),
    signup: () => calls.push("signup"),
    explore: () => calls.push("explore"),
    session: () => calls.push("session"),
    review: () => calls.push("review"),
    stats: () => calls.push("stats"),
    ranking: () => calls.push("ranking"),
    mypage: () => calls.push("mypage"),
  };

  // app.js 의 rootView 분기와 동일한 래퍼
  const rootView = (root, ctx) => (currentUser ? views.home(root, ctx) : views.landing(root, ctx));
  const routes = buildRoutes({ ...views, home: rootView });

  globalThis.window = { addEventListener: () => {} };
  globalThis.location = { hash: "#/", replace: (h) => { globalThis.location.hash = h; } };
  const fakeRoot = { replaceChildren: () => {} };

  const router = createRouter({ routes, root: fakeRoot, getUser: () => currentUser });
  router.render();
  assert.deepEqual(calls, ["landing"], "비로그인 시 #/ 는 소개 페이지(landing)를 그린다");
  assert.equal(globalThis.location.hash, "#/", "#/login 으로 리다이렉트하지 않는다");

  calls.length = 0;
  currentUser = { id: 1, nickname: "홍길동" };
  router.render();
  assert.deepEqual(calls, ["home"], "로그인 시 #/ 는 학습 홈(home)을 그린다");
});

test("app.js: 루트(/)에서 로그인 여부에 따라 homeView 와 landingView 를 분기한다", () => {
  const app = read("js/app.js");
  assert.match(app, /landingView/);
  assert.match(app, /getUser\(\)\s*\?\s*homeView\(root,\s*ctx\)\s*:\s*landingView\(root,\s*ctx\)/);
});
