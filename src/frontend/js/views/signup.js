/*
 * 2026-11-26 - voda-voca - 회원가입 화면: 닉네임 "중복 확인", 비밀번호 + 확인(일치 문구), 확인을 마쳐야 가입하기 활성화 (REQ-001, REQ-111, REQ-158)
 * 파일 위치: src/frontend/js/views/signup.js
 */

import { api } from "../core/api.js";
import {
  IDLE,
  canSubmitSignup,
  checkResultText,
  failCheck,
  finishCheck,
  invalidateOnEdit,
  startCheck,
} from "../core/availability.js";
import { alertBox, checkField, passwordField } from "../core/form.js";
import { brandLogo, button, h } from "../core/dom.js";
import { mapFieldErrors, passwordConfirmState, validateNickname, validatePassword } from "../core/validate.js";

const RATE_LIMITED = "확인 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
const CONFIRM_TONE_CLASS = { match: "text-emerald-700", mismatch: "text-red-600", empty: "text-zinc-500" };

/**
 * @param {HTMLElement} root
 * @param {{navigate: (path: string, query?: object) => void}} ctx
 */
export function signupView(root, { navigate }) {
  const nickname = checkField({
    id: "nickname",
    label: "닉네임",
    autocomplete: "nickname",
    hint: "2~30자. 다른 사람과 겹치지 않는 이름이어야 합니다.",
  });
  const password = passwordField({
    id: "password",
    label: "비밀번호",
    autocomplete: "new-password",
    hint: "8자 이상, 72바이트 이하 (한글은 한 글자가 3바이트)",
  });
  const confirm = passwordField({ id: "password-confirm", label: "비밀번호 확인", autocomplete: "new-password" });
  // 일치 여부는 오류가 아니라 안내다. 확인란 바로 아래에 aria-live 로 알린다.
  const confirmNote = h("p", { id: "password-confirm-status", class: "min-h-[1.25rem] text-sm text-zinc-500", "aria-live": "polite" });
  confirm.wrap.insertBefore(confirmNote, confirm.wrap.lastElementChild);
  confirm.input.setAttribute("aria-describedby", `${confirm.input.getAttribute("aria-describedby")} password-confirm-status`);

  const banner = alertBox();
  const submit = button({ type: "submit", full: true, disabled: true }, "가입하기");

  let nicknameState = IDLE;
  let busy = false;

  const values = () => ({
    nickname: nickname.input.value,
    password: password.input.value,
    confirm: confirm.input.value,
  });

  /** 상태 모델을 화면에 반영한다: 확인 결과 줄, 일치 문구, 확인 버튼과 가입하기 활성화. */
  function render() {
    nickname.setResult(checkResultText(nicknameState));
    nickname.checkButton.disabled = nicknameState.status === "checking";

    const { kind, message } = passwordConfirmState(password.input.value, confirm.input.value);
    confirmNote.textContent = message;
    confirmNote.className = `min-h-[1.25rem] text-sm ${CONFIRM_TONE_CLASS[kind]}`;

    const ready = canSubmitSignup(values(), { nicknameState });
    submit.disabled = busy || !ready.ok;
  }

  /** "중복 확인" 버튼: 규칙부터 보고, 서버에 중복 여부를 묻는다. 입력 도중 값이 바뀌면 오래된 응답은 무시된다. */
  async function runCheck() {
    const value = nickname.input.value;
    const invalid = validateNickname(value);
    nickname.setError(invalid);
    if (invalid) return;

    nicknameState = startCheck(value);
    render();
    try {
      const result = await api("/auth/check-nickname", { query: { nickname: value.trim() }, skipAuthRedirect: true });
      nicknameState = finishCheck(nicknameState, value, result.available);
    } catch (error) {
      const message =
        error.status === 429 ? RATE_LIMITED : error.status === 422 ? (error.fields[0]?.message ?? error.detail) : error.detail;
      nicknameState = failCheck(nicknameState, value, message);
    }
    render();
  }

  nickname.checkButton.addEventListener("click", runCheck);
  nickname.input.addEventListener("input", () => {
    nicknameState = invalidateOnEdit(nicknameState, nickname.input.value);
    nickname.setError(null);
    render();
  });
  for (const input of [password.input, confirm.input]) {
    input.addEventListener("input", () => {
      password.setError(null);
      render();
    });
  }

  async function onSubmit(event) {
    event.preventDefault();
    banner.hide();
    const v = values();
    nickname.setError(validateNickname(v.nickname));
    password.setError(validatePassword(v.password));
    const ready = canSubmitSignup(v, { nicknameState });
    if (!ready.ok) return;

    busy = true;
    render();
    try {
      await api("/auth/signup", {
        method: "POST",
        body: {
          nickname: v.nickname.trim(),
          password: v.password,
          password_confirm: v.confirm,
        },
        skipAuthRedirect: true,
      });
      navigate("/login", { signup: "done" });
    } catch (error) {
      if (error.status === 409 && error.code === "NICKNAME_TAKEN") {
        nickname.setError(error.detail);
        // 확인 버튼을 누른 뒤 다른 사람이 먼저 가입한 경우. 이 칸을 "이미 사용 중"으로 되돌린다.
        nicknameState = finishCheck(startCheck(v.nickname), v.nickname, false);
      } else if (error.status === 422) {
        const mapped = mapFieldErrors(error.fields, ["nickname", "password", "password_confirm"]);
        nickname.setError(mapped.nickname ?? null);
        password.setError(mapped.password ?? null);
        confirm.setError(mapped.password_confirm ?? null);
        banner.show(mapped._form ?? "입력값을 확인해 주세요.");
      } else {
        banner.show(error.detail);
      }
    } finally {
      busy = false;
      render();
    }
  }

  root.append(
    h(
      "section",
      { class: "mx-auto max-w-sm space-y-6 pt-6 rise-in" },
      h(
        "div",
        { class: "space-y-2 text-center" },
        brandLogo("lg"),
        h("h1", { class: "text-title tracking-tight text-zinc-900" }, "회원가입"),
        h("p", { class: "text-sm text-zinc-500" }, "이메일 없이 닉네임만 정하면 바로 시작할 수 있어요."),
      ),
      h(
        "div",
        { class: "card card-hero tone-accent" },
        h(
          "form",
          { class: "space-y-4", novalidate: true, onsubmit: onSubmit },
          nickname.wrap,
          password.wrap,
          confirm.wrap,
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
  render();
  nickname.input.focus();
}
