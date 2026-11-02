/*
 * 2026-11-02 - voda-voca - 회원가입 화면: 전송 전 검증, 서버 422·409 오류를 입력 칸별로 매핑 (REQ-001, REQ-111)
 * 파일 위치: src/frontend/js/views/signup.js
 */

import { api } from "../core/api.js";
import { field, alertBox } from "../core/form.js";
import { button, h } from "../core/dom.js";
import { mapFieldErrors, validateEmail, validateNickname, validatePassword } from "../core/validate.js";

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 */
export function signupView(root, { navigate }) {
  const email = field({ id: "email", label: "이메일", type: "email", autocomplete: "email", inputmode: "email" });
  const password = field({
    id: "password",
    label: "비밀번호",
    type: "password",
    autocomplete: "new-password",
    hint: "8자 이상, 72바이트 이하 (한글은 한 글자가 3바이트)",
  });
  const nickname = field({ id: "nickname", label: "닉네임", autocomplete: "nickname", maxlength: 50 });
  const banner = alertBox();
  const submit = button({ type: "submit", full: true }, "가입하기");
  const names = ["email", "password", "nickname"];

  async function onSubmit(event) {
    event.preventDefault();
    banner.hide();
    const values = {
      email: email.input.value.trim(),
      password: password.input.value,
      nickname: nickname.input.value.trim(),
    };
    const errors = {
      email: validateEmail(values.email),
      password: validatePassword(values.password),
      nickname: validateNickname(values.nickname),
    };
    email.setError(errors.email);
    password.setError(errors.password);
    nickname.setError(errors.nickname);
    if (Object.values(errors).some(Boolean)) return;

    submit.disabled = true;
    try {
      await api("/auth/signup", { method: "POST", body: values, skipAuthRedirect: true });
      navigate("/login", { signup: "done" });
    } catch (error) {
      if (error.status === 409) {
        email.setError(error.detail);
      } else if (error.status === 422) {
        const mapped = mapFieldErrors(error.fields, names);
        email.setError(mapped.email ?? null);
        password.setError(mapped.password ?? null);
        nickname.setError(mapped.nickname ?? null);
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
      { class: "mx-auto max-w-sm space-y-6 pt-6" },
      h("h1", { class: "text-2xl font-bold" }, "회원가입"),
      h(
        "form",
        { class: "space-y-4", novalidate: true, onsubmit: onSubmit },
        email.wrap,
        password.wrap,
        nickname.wrap,
        banner.el,
        submit,
      ),
      h(
        "p",
        { class: "text-center text-sm text-slate-600" },
        "이미 계정이 있나요? ",
        h("a", { href: "#/login", class: "inline-flex min-h-[44px] items-center font-semibold text-blue-700 underline" }, "로그인"),
      ),
    ),
  );
  email.input.focus();
}
