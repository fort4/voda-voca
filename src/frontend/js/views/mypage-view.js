/*
 * 2026-11-26 - voda-voca - 마이페이지 화면: 계정 정보, 비밀번호 변경, 회원 탈퇴 (계정 메뉴에서 연다, REQ-122, REQ-159, REQ-164)
 * 파일 위치: src/frontend/js/views/mypage-view.js
 */

import { api } from "../core/api.js";
import { button, h } from "../core/dom.js";
import { alertBox, passwordField } from "../core/form.js";
import { passwordChangeErrors, passwordChangeFailure, profileView } from "../core/mypage-model.js";
import { getUser } from "../core/state.js";
import { toast } from "../core/toast.js";
import { passwordConfirmState } from "../core/validate.js";
import { cardHeading } from "./components/card-heading.js";

const CONFIRM_TONE_CLASS = { match: "text-emerald-700", mismatch: "text-red-600", empty: "text-zinc-500" };

/**
 * @param {HTMLElement} root
 * @param {{withdraw: () => void}} ctx withdraw 는 확인 두 단계를 거쳐 탈퇴한다 (app.js)
 */
export function myPageView(root, { withdraw }) {
  const user = getUser();
  if (!user) return; // 라우터가 로그인 사용자만 들여보낸다
  root.append(
    h(
      "div",
      { class: "stack pb-4" },
      h("h1", { class: "text-title tracking-tight text-zinc-900" }, "마이페이지"),
      profileCard(profileView(user)),
      passwordCard(user),
      user.is_admin ? null : withdrawCard(withdraw), // 관리자 계정은 탈퇴할 수 없다 (서버도 403)
    ),
  );
}

/** @param {ReturnType<typeof profileView>} view */
function profileCard(view) {
  return h(
    "section",
    { class: "card tone-accent flex items-center gap-3", "aria-label": "계정 정보" },
    h("span", { class: "avatar-badge", "aria-hidden": "true" }, view.initial),
    h(
      "div",
      { class: "min-w-0" },
      h("p", { class: "flex flex-wrap items-center gap-2" }, h("span", { class: "break-all text-base font-bold text-zinc-900" }, view.nickname), h("span", { class: "chip-sm" }, view.role)),
      view.joined ? h("p", { class: "text-xs text-zinc-500" }, `가입일 ${view.joined}`) : null,
    ),
  );
}

/** @param {() => void} withdraw */
function withdrawCard(withdraw) {
  return h(
    "section",
    { class: "card tone-wrong space-y-3" },
    cardHeading({ iconName: "user-x", title: "회원 탈퇴" }),
    h("p", { class: "text-sm text-zinc-700" }, "계정과 북마크, 학습 기록이 영구 삭제됩니다. 되돌릴 수 없습니다."),
    button({ variant: "danger-soft", full: true, onClick: withdraw }, "회원 탈퇴"),
  );
}

/** @param {{nickname: string, is_admin?: boolean}} user */
function passwordCard(user) {
  const current = passwordField({ id: "current-password", label: "현재 비밀번호", autocomplete: "current-password" });
  const next = passwordField({
    id: "new-password",
    label: "새 비밀번호",
    autocomplete: "new-password",
    hint: "8자 이상, 72바이트 이하 (한글은 한 글자가 3바이트)",
  });
  const confirm = passwordField({ id: "new-password-confirm", label: "새 비밀번호 확인", autocomplete: "new-password" });
  const confirmNote = h("p", { id: "new-password-confirm-status", class: "min-h-[1.25rem] text-sm text-zinc-500", "aria-live": "polite" });
  confirm.wrap.insertBefore(confirmNote, confirm.wrap.lastElementChild);
  confirm.input.setAttribute("aria-describedby", `${confirm.input.getAttribute("aria-describedby")} new-password-confirm-status`);

  const fields = { current, next, confirm };
  const banner = alertBox();
  const submit = button({ type: "submit", full: true }, "비밀번호 변경");

  const values = () => ({ current: current.input.value, next: next.input.value, confirm: confirm.input.value });

  function renderConfirmNote() {
    const { kind, message } = passwordConfirmState(next.input.value, confirm.input.value);
    confirmNote.textContent = message;
    confirmNote.className = `min-h-[1.25rem] text-sm ${CONFIRM_TONE_CLASS[kind]}`;
  }

  /** @param {Record<string, string|undefined>} messages */
  function showErrors(messages) {
    for (const [name, field] of Object.entries(fields)) field.setError(messages[name] ?? null);
    if (messages.banner) banner.show(messages.banner);
  }

  async function onSubmit(event) {
    event.preventDefault();
    if (submit.disabled) return;
    banner.hide();
    const v = values();
    const errors = passwordChangeErrors(v);
    // 확인란이 틀린 것은 바로 아래 안내 줄이 이미 알리므로 같은 문장을 두 번 보이지 않는다
    if (errors.confirm && passwordConfirmState(v.next, v.confirm).kind === "mismatch") delete errors.confirm;
    showErrors(errors);
    if (Object.keys(passwordChangeErrors(v)).length > 0) return;

    submit.disabled = true;
    try {
      await api("/auth/me/password", {
        method: "PUT",
        body: { current_password: v.current, new_password: v.next, new_password_confirm: v.confirm },
      });
      form.reset();
      for (const field of Object.values(fields)) field.hide();
      renderConfirmNote();
      toast("비밀번호를 바꿨어요");
    } catch (error) {
      if (error.status !== 401) showErrors(passwordChangeFailure(error)); // 401 은 공통 처리(로그인 화면)로 간다
    } finally {
      submit.disabled = false;
    }
  }

  for (const [name, field] of Object.entries(fields)) {
    field.input.addEventListener("input", () => {
      field.setError(null);
      if (name !== "current") renderConfirmNote();
    });
  }

  const form = /** @type {HTMLFormElement} */ (
    h(
      "form",
      { class: "space-y-4", novalidate: true, onsubmit: onSubmit },
      // 비밀번호 관리자가 어느 계정의 비밀번호인지 알 수 있게 닉네임을 함께 둔다
      h("input", { type: "text", name: "username", autocomplete: "username", value: user.nickname, class: "hidden", readonly: true, tabindex: "-1", "aria-hidden": "true" }),
      current.wrap,
      next.wrap,
      confirm.wrap,
      banner.el,
      submit,
    )
  );

  return h(
    "section",
    { class: "card space-y-4" },
    cardHeading({ iconName: "lock", title: "비밀번호 변경" }),
    user.is_admin ? h("p", { class: "text-sm text-zinc-700" }, "처음 받은 비밀번호를 그대로 쓰고 있다면 지금 바꿔 주세요.") : null,
    h("p", { class: "text-xs text-zinc-500" }, "바꾸면 다른 기기에서 로그인한 상태는 해제됩니다."),
    form,
  );
}
