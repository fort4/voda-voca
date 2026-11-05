/*
 * 2026-11-05 - voda-voca - 비동기 화면 로더: 스켈레톤 → 데이터 → 그리기, 실패하면 다시 시도 안내. 화면을 떠난 뒤 도착한 응답은 버린다
 * 파일 위치: src/frontend/js/views/components/loader.js
 */

import { button, clear, notice, refreshIcons, skeleton } from "../../core/dom.js";

/**
 * @template T
 * @param {HTMLElement} root
 * @param {() => Promise<T>} load
 * @param {(data: T) => void} render root 에 그린다
 * @returns {() => void} 화면을 떠날 때의 정리 함수
 */
export function mountLoader(root, load, render) {
  let disposed = false;

  function run() {
    clear(root);
    root.append(skeleton(3));
    load().then(
      (data) => {
        if (disposed) return;
        clear(root);
        render(data);
        refreshIcons();
      },
      (error) => {
        if (disposed || error?.name === "AbortError") return;
        clear(root);
        root.append(
          notice({
            iconName: "wifi-off",
            title: "불러오지 못했어요",
            text: error?.detail ?? "잠시 후 다시 시도해 주세요.",
            action: button({ variant: "primary", onClick: run }, "다시 시도"),
          }),
        );
        refreshIcons();
      },
    );
  }

  run();
  return () => {
    disposed = true;
  };
}
