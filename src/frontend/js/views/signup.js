/*
 * 2026-11-02 - voda-voca - 회원가입 화면: 닉네임 + 비밀번호 단일 폼, 닉네임 중복 409 는 닉네임 칸에 표시 (REQ-001, REQ-111)
 * 파일 위치: src/frontend/js/views/signup.js
 */

import { api } from "../core/api.js";
import { field, alertBox } from "../core/form.js";
import { button, h } from "../core/dom.js";
import { mapFieldErrors, validateNickname, validatePassword } from "../core/validate.js";

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 */
export function signupView(root, { navigate }) {
  const nickname = field({
    id: "nickname",
    label: "닉네임",
    autocomplete: "username",
    hint: "2~30자. 다른 사람과 겹치지 않는 이름이어야 합니다.",
  });
  const password = field({
    id: "password",
    label: "비밀번호",
    type: "password",
    autocomplete: "new-password",
    hint: "8자 이상, 72바이트 이하 (한글은 한 글자가 3바이트)",
  });
  const banner = alertBox();
  const submit = button({ type: "submit", full: true }, "가입하기");

  async function onSubmit(event) {
    event.preventDefault();
    banner.hide();
    const values = { nickname: nickname.input.value.trim(), password: password.input.value };
    const nicknameError = validateNickname(values.nickname);
    const passwordError = validatePassword(values.password);
    nickname.setError(nicknameError);
    password.setError(passwordError);
    if (nicknameError || passwordError) return;

    submit.disabled = true;
    try {
      await api("/auth/signup", { method: "POST", body: values, skipAuthRedirect: true });
      navigate("/login", { signup: "done" });
    } catch (error) {
      if (error.status === 409) {
        nickname.setError(error.detail);
      } else if (error.status === 422) {
        const mapped = mapFieldErrors(error.fields, ["nickname", "password"]);
        nickname.setError(mapped.nickname ?? null);
        password.setError(mapped.password ?? null);
        banner.show(mapped._form ?? "입력값을 확인해 주세요.");
      } else {
        banner.show(error.detail);
      }
    } finally {
      submit.disabled = false;
    }
  }

  root.append(
    h(
      "section",
      { class: "mx-auto max-w-sm space-y-6 pt-6 rise-in" },
      h(
        "div",
        { class: "space-y-2 text-center" },
        h("div", { class: "brand-mark mx-auto h-12 w-12 rounded-2xl" }, "보"),
        h("h1", { class: "text-2xl font-bold tracking-tight text-zinc-900" }, "회원가입"),
        h("p", { class: "text-sm text-zinc-500" }, "이메일 없이 닉네임만 정하면 바로 시작할 수 있어요."),
      ),
      h(
        "div",
        { class: "surface p-6" },
        h(
          "form",
          { class: "space-y-4", novalidate: true, onsubmit: onSubmit },
          nickname.wrap,
          password.wrap,
          banner.el,
          submit,
        ),
      ),
      h(
        "p",
        { class: "text-center text-sm text-zinc-500" },
        "이미 계정이 있나요? ",
        h("a", { href: "#/login", class: "focus-ring inline-flex min-h-[44px] items-center font-semibold text-indigo-600 hover:text-indigo-700" }, "로그인"),
      ),
    ),
  );
  nickname.input.focus();
}
