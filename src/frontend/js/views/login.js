/*
 * 2026-11-02 - voda-voca - 로그인 화면: 세션 쿠키 로그인, 401 안내, 429 시 버튼 비활성화와 초 단위 카운트다운 (REQ-001, REQ-121)
 * 파일 위치: src/frontend/js/views/login.js
 */

import { api } from "../core/api.js";
import { formatRetry } from "../core/format.js";
import { field, alertBox } from "../core/form.js";
import { button, h } from "../core/dom.js";
import { setUser } from "../core/state.js";
import { toast } from "../core/toast.js";
import { safeNext } from "../core/router.js";
import { mapFieldErrors, validateEmail } from "../core/validate.js";

/**
 * @param {HTMLElement} root
 * @param {{query: Record<string, string>, navigate: (path: string, query?: object) => void}} ctx
 * @returns {() => void} 화면을 떠날 때 타이머를 정리한다
 */
export function loginView(root, { query, navigate }) {
  const email = field({ id: "email", label: "이메일", type: "email", autocomplete: "username", inputmode: "email" });
  const password = field({ id: "password", label: "비밀번호", type: "password", autocomplete: "current-password" });
  const banner = alertBox();
  const note = h("p", { class: "min-h-[1.5rem] text-sm text-slate-600", "aria-live": "polite" });
  const submit = button({ type: "submit", full: true }, "로그인");

  let timer = null;
  let retryUntil = 0;

  /** 429 대기 중에는 제출 버튼을 막고, 남은 초를 안내한다. */
  function tick() {
    const left = Math.ceil((retryUntil - Date.now()) / 1000);
    if (left <= 0) {
      stopCooldown();
      return;
    }
    note.textContent = formatRetry(left);
  }

  function startCooldown(seconds) {
    stopCooldown();
    retryUntil = Date.now() + seconds * 1000;
    submit.disabled = true;
    tick();
    timer = setInterval(tick, 1000);
  }

  function stopCooldown() {
    if (timer !== null) clearInterval(timer);
    timer = null;
    submit.disabled = false;
    note.textContent = "";
  }

  async function onSubmit(event) {
    event.preventDefault();
    banner.hide();
    const emailValue = email.input.value.trim();
    const passwordValue = password.input.value;
    const emailError = validateEmail(emailValue);
    email.setError(emailError);
    password.setError(passwordValue ? null : "비밀번호를 입력해 주세요.");
    if (emailError || !passwordValue) return;

    submit.disabled = true;
    try {
      const user = await api("/auth/login", {
        method: "POST",
        body: { email: emailValue, password: passwordValue },
        skipAuthRedirect: true,
      });
      setUser(user);
      navigate(safeNext(query.next));
    } catch (error) {
      if (error.status === 429) {
        banner.show("로그인 시도가 너무 많습니다. 잠시 후 다시 시도해 주세요.");
        startCooldown(error.retryAfter ?? 60);
        return;
      }
      if (error.status === 401) {
        password.input.value = "";
        banner.show(error.detail);
      } else if (error.status === 422) {
        const mapped = mapFieldErrors(error.fields, ["email", "password"]);
        email.setError(mapped.email ?? null);
        password.setError(mapped.password ?? null);
        banner.show(mapped._form ?? "입력값을 확인해 주세요.");
      } else {
        banner.show(error.detail);
      }
    } finally {
      if (timer === null) submit.disabled = false;
    }
  }

  const form = h(
    "form",
    { class: "space-y-4", novalidate: true, onsubmit: onSubmit },
    email.wrap,
    password.wrap,
    banner.el,
    note,
    submit,
  );

  root.append(
    h(
      "section",
      { class: "mx-auto max-w-sm space-y-6 pt-6" },
      h("h1", { class: "text-2xl font-bold" }, "로그인"),
      form,
      h(
        "p",
        { class: "text-center text-sm text-slate-600" },
        "계정이 없으신가요? ",
        h("a", { href: "#/signup", class: "inline-flex min-h-[44px] items-center font-semibold text-blue-700 underline" }, "회원가입"),
      ),
    ),
  );

  if (query.signup === "done") toast("가입이 완료되었습니다. 로그인해 주세요.");
  email.input.focus();
  return () => stopCooldown();
}

