/*
 * 2026-11-10 - voda-voca - 세션 카드의 북마크 버튼: 44px 아이콘 버튼, 눌림 상태(aria-pressed), 저장소 변경을 구독해 스스로 갱신
 * 파일 위치: src/frontend/js/views/components/bookmark-button.js
 */

import { h, icon } from "../../core/dom.js";

/**
 * 카드 오른쪽 위에 놓는 북마크 토글. 상태는 저장소가 갖고, 버튼은 구독으로 따라간다.
 * @param {{wordId: number, term: string, store: ReturnType<typeof import("../../core/bookmark-store.js").createBookmarkStore>, onError: (error: unknown) => void}} opts
 * @returns {HTMLButtonElement}
 */
export function bookmarkButton({ wordId, term, store, onError }) {
  const label = (on) => (on ? `${term} 북마크 해제` : `${term} 북마크에 추가`);
  const el = /** @type {HTMLButtonElement} */ (
    h(
      "button",
      {
        type: "button",
        class: "btn btn-ghost btn-icon star-toggle focus-ring",
        "aria-pressed": String(store.isBookmarked(wordId)),
        "aria-label": label(store.isBookmarked(wordId)),
        onclick: (event) => {
          event.stopPropagation(); // 플래시카드 위에서 눌러도 카드가 뒤집히지 않게
          store.toggle(wordId).catch(onError);
        },
      },
      icon("bookmark", "h-5 w-5"),
    )
  );
  const off = store.subscribe((id, on) => {
    if (!el.isConnected) return off(); // 화면이 다시 그려져 버튼이 떨어져 나가면 구독을 푼다
    if (id !== wordId) return;
    el.setAttribute("aria-pressed", String(on));
    el.setAttribute("aria-label", label(on));
    el.toggleAttribute("aria-busy", store.isPending(id));
  });
  return el;
}
