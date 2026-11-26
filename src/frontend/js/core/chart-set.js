/*
 * 2026-11-26 - voda-voca - 차트 수명 관리: 한 화면의 차트를 함께 만들고, 테마가 바뀌면 다시 그리고, 화면을 떠날 때 정리한다 (의존성 주입, REQ-132, REQ-155)
 * 파일 위치: src/frontend/js/core/chart-set.js
 */

/**
 * 루트의 dark 클래스가 실제로 바뀔 때만 알린다. SweetAlert2 도 루트에 클래스를 붙이므로 그 변화는 무시한다.
 * @param {{classList: {contains(name: string): boolean}}} root
 * @param {typeof MutationObserver} Observer
 * @param {() => void} listener
 * @returns {() => void} 감시 중단
 */
export function watchDarkClass(root, Observer, listener) {
  let dark = root.classList.contains("dark");
  const observer = new Observer(() => {
    const next = root.classList.contains("dark");
    if (next === dark) return;
    dark = next;
    listener();
  });
  observer.observe(root, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

/**
 * @param {{
 *   ChartCtor: (new (canvas: any, config: object) => {destroy(): void})|undefined,
 *   readPalette: () => object,
 *   observeTheme: (listener: () => void) => () => void,
 *   reducedMotion: () => boolean,
 * }} deps
 */
export function createChartSet({ ChartCtor, readPalette, observeTheme, reducedMotion }) {
  /** @type {Array<{canvas: any, build: Function, onFail?: () => void, chart: any}>} */
  let entries = [];
  let stopWatching = null;
  let destroyed = false;

  function draw(entry, animate) {
    entry.chart?.destroy();
    entry.chart = null;
    try {
      entry.chart = new ChartCtor(entry.canvas, entry.build(readPalette(), { animate }));
    } catch (error) {
      console.error("차트를 그리지 못했다", error);
      entry.onFail?.();
    }
  }

  return {
    /** @param {any} canvas @param {(palette: object, options: {animate: boolean}) => object} build @param {() => void} [onFail] */
    add(canvas, build, onFail) {
      entries.push({ canvas, build, onFail, chart: null });
    },
    /** 캔버스가 문서에 붙은 뒤에 부른다 (Chart.js 는 부모 크기를 읽는다). */
    mount() {
      if (destroyed || entries.length === 0) return;
      if (!ChartCtor) {
        for (const entry of entries) entry.onFail?.();
        return;
      }
      const animate = !reducedMotion();
      for (const entry of entries) draw(entry, animate);
      stopWatching = observeTheme(() => {
        for (const entry of entries) draw(entry, false);
      });
    },
    chartOf(canvas) {
      return entries.find((entry) => entry.canvas === canvas)?.chart ?? null;
    },
    destroy() {
      destroyed = true;
      stopWatching?.();
      stopWatching = null;
      for (const entry of entries) entry.chart?.destroy();
      entries = [];
    },
  };
}
