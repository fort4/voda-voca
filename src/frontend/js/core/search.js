/*
 * 2026-11-02 - voda-voca - 표제어 검색 파이프라인: 300ms trailing 디바운스, 이전 요청 취소, 증가 번호로 오래된 응답 버림 (REQ-009, REQ-103)
 * 파일 위치: src/frontend/js/core/search.js
 */

/**
 * @template T
 * @param {{
 *   run: (query: string, signal: AbortSignal) => Promise<T>,
 *   onLoading: (query: string) => void,
 *   onResult: (data: T, query: string) => void,
 *   onError: (error: unknown, query: string) => void,
 *   delayMs?: number
 * }} opts
 */
export function createSearch({ run, onLoading, onResult, onError, delayMs = 300 }) {
  let timer = null;
  let controller = null;
  let seq = 0;
  let lastFired = null;

  /** 실제 요청을 보낸다. 같은 검색어가 연속으로 오면 다시 보내지 않는다. */
  function fire(query, force = false) {
    timer = null;
    if (!force && query === lastFired) return;
    lastFired = query;
    controller?.abort();
    controller = new AbortController();
    seq += 1;
    const mine = seq;
    onLoading(query);
    run(query, controller.signal).then(
      (data) => {
        if (mine !== seq) return; // 더 최신 요청이 있으므로 이 응답은 버린다
        onResult(data, query);
      },
      (error) => {
        if (mine !== seq || error?.name === "AbortError") return;
        lastFired = null; // 실패한 검색어는 다시 입력되면 재시도한다
        onError(error, query);
      },
    );
  }

  return {
    /**
     * 입력이 바뀔 때마다 부른다. 마지막 입력 뒤 delayMs 가 지나야 요청한다.
     * @param {string} raw
     */
    setQuery(raw) {
      const query = raw.trim();
      if (timer !== null) clearTimeout(timer);
      timer = setTimeout(() => fire(query), delayMs);
    },
    /** 디바운스를 건너뛰고 즉시 검색한다 (지우기 버튼, 화면 진입). */
    flush(raw) {
      if (timer !== null) clearTimeout(timer);
      fire(raw.trim(), true);
    },
    /** 대기 중인 검색과 진행 중인 요청을 모두 취소한다 (화면을 떠날 때). */
    cancel() {
      if (timer !== null) clearTimeout(timer);
      timer = null;
      controller?.abort();
      controller = null;
      seq += 1;
    },
  };
}
