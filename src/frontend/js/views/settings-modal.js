/*
 * 2026-11-10 - voda-voca - 학습 설정 모달: 계정 메뉴의 '학습 설정'에서 열고 퀴즈·플래시카드 문항 수와 오늘의 목표를 바꾼다 (REQ-147)
 * 파일 위치: src/frontend/js/views/settings-modal.js
 */

import { clear, h } from "../core/dom.js";
import { settingsStore } from "../core/settings-store.js";
import { getUser } from "../core/state.js";
import { renderSettingsForm } from "./components/settings-form.js";

const LOAD_ERROR = "설정을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.";
const SAVE_ERROR = "저장하지 못했어요. 다시 시도해 주세요.";

/**
 * 모달을 연다. 값은 고르는 즉시 저장되므로 '닫기' 버튼만 있다.
 * 열려 있는 SweetAlert2 팝업은 하나뿐이라, 오류는 토스트가 아니라 모달 안에 보인다.
 */
export function openSettingsModal() {
  const Swal = globalThis.Swal;
  const user = getUser();
  if (!Swal || !user) return Promise.resolve();

  const body = h("div", { class: "text-left" });
  /** @type {"loading"|"ready"|"failed"} */
  let phase = "loading";
  let saveFailed = false;
  let unsubscribe = () => {};

  /** 다시 그린다. 키보드로 고르던 칩에는 포커스를 되돌린다. */
  function paint() {
    const focused = body.querySelector("[data-setting]:focus")?.getAttribute("data-setting");
    clear(body);
    if (phase === "loading") {
      body.append(h("p", { class: "text-sm text-zinc-600" }, "불러오는 중이에요."));
      return;
    }
    if (phase === "failed") {
      body.append(h("p", { role: "alert", class: "text-sm text-zinc-600" }, LOAD_ERROR));
      return;
    }
    body.append(
      h("p", { class: "mb-3 text-sm text-zinc-600" }, "한 번에 풀 문항 수와 하루 목표예요. 고르면 바로 저장돼요."),
      renderSettingsForm({ settings: settingsStore.get(), onChange: change }),
      // 오류 줄은 비어 있어도 높이를 남겨 두어 메시지가 나타날 때 모달이 흔들리지 않는다
      h("p", { role: "alert", class: "mt-3 min-h-[1.25rem] text-sm font-medium text-red-600" }, saveFailed ? SAVE_ERROR : ""),
    );
    if (focused) body.querySelector(`[data-setting="${focused}"]`)?.focus();
  }

  async function change(key, value) {
    saveFailed = false;
    saveFailed = !(await settingsStore.change(key, value));
    paint();
  }

  return Swal.fire({
    title: "학습 설정",
    html: body,
    showConfirmButton: true,
    confirmButtonText: "닫기",
    didOpen: () => {
      unsubscribe = settingsStore.subscribe(() => phase === "ready" && paint());
      paint();
      settingsStore.load(user.id).then(
        () => {
          phase = "ready";
          paint();
        },
        () => {
          phase = "failed";
          paint();
        },
      );
    },
    willClose: () => unsubscribe(),
  });
}
