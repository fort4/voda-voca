/*
 * 2026-11-11 - voda-voca - 환경 설정 모달: 계정 메뉴의 '환경 설정'에서 열고 효과음과 다크 모드를 스위치로 바꾼다 (헤더 버튼을 옮김)
 * 파일 위치: src/frontend/js/views/preferences-modal.js
 */

import { clear, h, icon } from "../core/dom.js";
import { preferenceRows } from "../core/preferences-model.js";
import { isMuted, subscribeMute, toggleMute } from "../core/sound.js";

/**
 * 모달을 연다. 스위치는 누르는 즉시 적용·저장되므로 '닫기' 버튼만 있다.
 * @param {{themeManager: {current: () => "light"|"dark", toggle: () => "light"|"dark"}}} deps
 */
export function openPreferencesModal({ themeManager }) {
  const Swal = globalThis.Swal;
  if (!Swal) return Promise.resolve();

  const body = h("div", { class: "text-left" });
  let unsubscribe = () => {};

  /** 스위치를 누르면 해당 설정을 바꾼다. 효과음은 구독으로, 테마는 직접 다시 그린다. */
  const actions = {
    sound: () => toggleMute(),
    theme: () => {
      themeManager.toggle();
      paint();
    },
  };

  /** 다시 그린다. 키보드로 누르던 스위치에는 포커스를 되돌린다. */
  function paint() {
    const focused = body.querySelector("[data-pref]:focus")?.getAttribute("data-pref");
    clear(body);
    body.append(
      h(
        "div",
        { class: "pref-list" },
        ...preferenceRows({ muted: isMuted(), theme: themeManager.current() }).map((row) =>
          h(
            "button",
            {
              type: "button",
              role: "switch",
              "aria-checked": String(row.checked),
              "data-pref": row.id,
              class: "pref-row focus-ring min-h-[44px]",
              onclick: actions[row.id],
            },
            h("span", { class: "pref-icon", "aria-hidden": "true" }, icon(row.icon, "h-5 w-5")),
            h("span", { class: "min-w-0 flex-1" }, h("span", { class: "block text-body font-semibold text-zinc-900" }, row.label), h("span", { class: "block text-xs text-zinc-500" }, row.description)),
            h("span", { class: "switch-track", "aria-hidden": "true" }, h("span", { class: "switch-thumb" })),
          ),
        ),
      ),
    );
    if (focused) body.querySelector(`[data-pref="${focused}"]`)?.focus();
  }

  return Swal.fire({
    title: "환경 설정",
    html: body,
    showConfirmButton: true,
    confirmButtonText: "닫기",
    didOpen: () => {
      unsubscribe = subscribeMute(paint); // 다른 곳에서 바뀌어도 스위치가 따라온다
      paint();
    },
    willClose: () => unsubscribe(),
  });
}
