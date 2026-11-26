/*
 * 2026-11-26 - voda-voca - UI 전면 개선(A·B·C) 회귀 테스트: 로고 배지, 모달 테마 통일, 반응형 2열 그리드·중앙 시트, 복습함 모드 전환, 통계→복습 동선, 헤더 대칭
 * 파일 위치: src/frontend/tests/ui-overhaul.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");
const css = read("css/app.css").replace(/\/\*[\s\S]*?\*\//g, "");

test("A·C: 로그인·회원가입 화면은 'VODA' 텍스트 대신 brandLogo() 아이콘과 .card 표면을 쓴다", () => {
  const dom = read("js/core/dom.js");
  assert.match(dom, /export function brandLogo\(/);
  for (const file of ["js/views/login.js", "js/views/signup.js"]) {
    const src = read(file);
    assert.match(src, /brandLogo\(/, `${file} 은 brandLogo() 를 써야 한다`);
    assert.doesNotMatch(src, /"VODA"/, `${file} 에 깨진 VODA 글자 배지가 남아 있다`);
    assert.match(src, /\bcard\b/, `${file} 은 .card 컴포넌트를 써야 한다`);
  }
});

test("A·C: SweetAlert2 확인 모달과 팝업 버튼·입력창은 앱 디자인 토큰(#4f46e5, .swal2-confirm, .swal2-input)과 통일된다", () => {
  const toastSrc = read("js/core/toast.js");
  assert.doesNotMatch(toastSrc, /#2563eb/, "confirmDialog 에 타사 파란색(#2563eb) 대신 인디고(#4f46e5)를 쓴다");
  assert.match(toastSrc, /#4f46e5/);
  assert.match(css, /\.swal2-popup\s*\{[^}]*border-radius:\s*var\(--radius-card\)/);
  assert.match(css, /\.swal2-styled\.swal2-confirm[^{]*\{[^}]*border-radius:\s*var\(--radius-control\)/);
  assert.match(css, /\.swal2-input\s*\{[^}]*border-radius:\s*var\(--radius-control\)/);
});

test("A: 미사용 레거시 CSS(.level-tag, .surface-interactive)가 제거되어 스타일시트가 정돈되었다", () => {
  assert.doesNotMatch(css, /\.level-tag\b/);
  assert.doesNotMatch(css, /\.surface-interactive\b/);
});

test("B·C: 탐색 화면의 단어장 카드 목록은 넓은 화면에서 2열 격자(sm:grid-cols-2)로 배치된다", () => {
  const explore = read("js/views/explore-view.js");
  assert.match(explore, /sm:grid-cols-2/);
});

test("B·C: 단어 프리뷰 시트는 모바일에서 바텀시트, sm(640px) 이상에서 가운데 모달로 열리고 단어 행에 .word-item 을 쓴다", () => {
  const sheet = read("js/views/components/word-sheet.js");
  assert.match(sheet, /sm:items-center/);
  assert.match(sheet, /sm:rounded-2xl/);
  assert.match(sheet, /word-item/);
  assert.match(css, /\.word-item\s*\{/);
});

test("B: 복습함 화면에서도 학습 방식(퀴즈/플래시카드) 토글을 보여 주고 변경 시 저장한다", () => {
  const review = read("js/views/review-view.js");
  assert.match(review, /renderModeToggle\(/);
  assert.match(review, /saveMode\(/);
});

test("B·C: 통계와 순위 화면은 상단 제목(h1.text-title)과 .stack 구조를 갖추고, 통계에서 복습함으로 바로 이동할 수 있다", () => {
  const stats = read("js/views/stats-view.js");
  const ranking = read("js/views/ranking-view.js");
  assert.match(stats, /text-title/);
  assert.match(ranking, /text-title/);
  assert.match(stats, /"\/review"/, "통계의 오답 영역에서 복습함으로 이동하는 동선이 있다");
});

test("A: 세션 진행 헤더의 중단(✕) 버튼은 발음 버튼과 같은 .btn.btn-ghost.btn-icon 규격을 쓴다", () => {
  const header = read("js/views/components/progress-header.js");
  assert.match(header, /btn btn-ghost btn-icon/);
});

test("A: 마이페이지 비밀번호 변경 카드도 의미 색(tone-accent)을 갖춰 아이콘 배지가 통일된다", () => {
  const mypage = read("js/views/mypage-view.js");
  const pwFn = mypage.slice(mypage.indexOf("function passwordCard"));
  assert.match(pwFn, /card tone-accent/);
});

// ---------- 2026-11-26 화면 확인에서 찾은 결함의 회귀 검사 ----------

test("카드 상단에 색 강조선을 두지 않는다 (사용자 지시)", () => {
  assert.doesNotMatch(css, /card-hero/);
  assert.doesNotMatch(css, /\.card[^{}]*\{[^}]*border-top[^;}]*var\(--(tone|accent)/);
  for (const file of ["js/views/home-view.js", "js/views/review-view.js", "js/views/login.js", "js/views/signup.js"]) {
    assert.doesNotMatch(read(file), /card-hero/, file);
  }
});

test("통계의 오답 복습 버튼은 복습함의 틀린 단어 탭으로 간다", () => {
  assert.match(read("js/views/stats-view.js"), /navigate\("\/review",\s*\{\s*tab:\s*"wrong"\s*\}\)/);
  assert.match(read("js/views/review-view.js"), /this\.active = initialReviewTab\(ctx\.query\)/);
});

test("위험 확인 버튼은 어느 창에서나 빨간 아래 테두리를 쓴다", () => {
  assert.match(css, /\.swal2-styled\.swal2-confirm\.swal2-danger\s*\{[^}]*box-shadow:\s*0 3px 0 var\(--btn-danger-edge\)/);
  assert.match(read("js/core/toast.js"), /customClass:\s*danger \? \{ confirmButton: "swal2-danger" \} : \{\}/);
  const app = read("js/app.js");
  const reds = (app.match(/confirmButtonColor: "#dc2626"/g) ?? []).length;
  assert.equal((app.match(/confirmButton: "swal2-danger"/g) ?? []).length, reds, "빨간 확인 버튼마다 위험 클래스를 붙인다");
});
