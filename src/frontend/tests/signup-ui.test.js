/*
 * 2026-11-26 - voda-voca - 가입·로그인 화면 구성 검사: 닉네임 확인 버튼, 비밀번호 확인 문구, 이메일 없는 간편 형태, 접근성 (REQ-158)
 * 파일 위치: src/frontend/tests/signup-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

test("checkField: 입력 옆 확인 버튼(44px, type=button)과 aria-live 결과 줄을 만든다", () => {
  const src = read("js/core/form.js");
  assert.match(src, /export function checkField\(/);
  const body = src.slice(src.indexOf("export function checkField("));
  assert.match(body, /type:\s*"button"/, "확인 버튼이 폼을 제출하면 안 된다");
  assert.match(body, /min-h-\[44px\]/);
  assert.match(body, /aria-live/);
  assert.match(src, /ok:\s*"text-emerald-700"/, "사용 가능은 초록 (다크 오버라이드가 있는 색)");
  assert.match(src, /bad:\s*"text-red-600"/, "불가는 빨강");
});

test("가입 화면: 닉네임·비밀번호·비밀번호 확인 세 칸이고 확인 버튼은 닉네임에만 있다", () => {
  const src = read("js/views/signup.js");
  for (const id of ['"nickname"', '"password"', '"password-confirm"']) {
    assert.ok(src.includes(`id: ${id}`), `입력 id ${id}`);
  }
  assert.equal((src.match(/checkField\(/g) ?? []).length, 1, "닉네임 한 곳");
  assert.equal((src.match(/passwordField\(/g) ?? []).length, 2, "비밀번호와 확인란 모두 보기 토글");
  assert.match(src, /autocomplete:\s*"new-password"/);
});

test("가입 화면: 이메일 입력·요청이 없다 (안내 문구의 '이메일 없이'만 허용)", () => {
  const src = read("js/views/signup.js");
  assert.doesNotMatch(src, /email/i, "코드에 email 식별자가 없다");
  assert.equal((src.match(/이메일/g) ?? []).length, 1, "'이메일 없이 닉네임만' 안내 한 곳");
});

test("가입 화면: 확인 버튼은 서버 확인 API 를 부르고 결과를 상태 모델로 처리한다", () => {
  const src = read("js/views/signup.js");
  assert.match(src, /\/auth\/check-nickname/);
  assert.doesNotMatch(src, /check-email/);
  assert.match(src, /finishCheck\(/);
  assert.match(src, /invalidateOnEdit\(/, "값을 고치면 확인 결과를 무효로 돌린다");
  assert.match(src, /skipAuthRedirect:\s*true/, "비로그인 호출이라 401 리디렉션을 하지 않는다");
});

test("가입 화면: 비밀번호 확인란은 입력 즉시 일치 여부 문구를 보인다", () => {
  const src = read("js/views/signup.js");
  assert.match(src, /passwordConfirmState\(/);
  assert.match(src, /addEventListener\("input"/);
});

test("가입 화면: 닉네임 확인을 마치기 전에는 가입하기를 막고 이유를 알린다", () => {
  const src = read("js/views/signup.js");
  assert.match(src, /canSubmitSignup\(/);
  assert.match(src, /submit\.disabled/);
});

test("가입 요청 본문은 nickname, password, password_confirm 이다", () => {
  const src = read("js/views/signup.js");
  assert.match(src, /password_confirm/);
  assert.match(src, /"\/auth\/signup"/);
});

test("가입 409 는 X-Error-Code(NICKNAME_TAKEN)로 닉네임 칸에 표시한다", () => {
  const src = read("js/views/signup.js");
  assert.match(src, /NICKNAME_TAKEN/);
  assert.match(src, /error\.code/);
});

test("가입 화면 문구: 이메일 없이 닉네임만 정하면 된다고 안내한다", () => {
  assert.match(read("js/views/signup.js"), /이메일 없이 닉네임/);
});

test("로그인 화면은 닉네임 + 비밀번호다 (이메일 칸 없음)", () => {
  const src = read("js/views/login.js");
  assert.match(src, /id:\s*"nickname"/);
  assert.match(src, /닉네임과 비밀번호로 로그인/);
  assert.doesNotMatch(src, /email|이메일/i);
});

test("계정 정보 타입에 email 이 없다", () => {
  assert.doesNotMatch(read("js/core/state.js"), /email/);
});

test("가입하기 버튼 아래에는 안내 문구 줄이 없다 (오류는 각 입력 칸 아래에만 보인다)", () => {
  const src = read("js/views/signup.js");
  assert.doesNotMatch(src, /submitHint/);
  assert.doesNotMatch(src, /ready\.reason/);
});

test("확인 버튼의 이름은 '중복 확인'이다 ('사용 가능 확인'이라는 이름은 쓰지 않는다)", () => {
  assert.match(read("js/core/form.js"), /buttonLabel = "중복 확인"/);
  for (const file of ["js/core/form.js", "js/views/signup.js", "js/core/availability.js"]) {
    assert.doesNotMatch(read(file), /사용 가능 확인/, file);
  }
});

test("가입·로그인 화면을 오가는 링크는 44×44px 터치 타깃이다 (REQ-114)", () => {
  for (const [file, href] of [["js/views/signup.js", "#/login"], ["js/views/login.js", "#/signup"]]) {
    const link = read(file).split("\n").find((line) => line.includes(`h("a", { href: "${href}"`)) ?? "";
    for (const cls of ["min-h-[44px]", "min-w-[44px]", "justify-center"]) {
      assert.ok(link.includes(cls), `${file} 링크에 ${cls} 가 없다`);
    }
  }
});
