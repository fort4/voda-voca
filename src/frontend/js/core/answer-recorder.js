/*
 * 2026-11-03 - voda-voca - 퀴즈 답 기록 큐: 고른 답을 순서대로 서버에 보내고, 일시 오류는 다시 시도하고, 소용없는 오류는 실패로 분리한다 (이슈 #8)
 * 파일 위치: src/frontend/js/core/answer-recorder.js
 */

export const DEFAULT_RETRY_DELAYS_MS = [500, 1500, 3000, 6000];

/** @param {number} ms */
const defaultSleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * 다시 시도하면 성공할 수 있는 오류인가. 네트워크 단절(status 0), 요청 과다(429), 서버 오류(5xx)만 해당한다.
 * 이미 끝난 퀴즈, 만료, 잠긴 답 같은 4xx 는 다시 보내도 같은 결과이므로 바로 실패로 분리한다.
 * @param {any} error
 * @returns {boolean}
 */
export function isRetryable(error) {
  const status = error?.status;
  return status === 0 || status === 429 || (typeof status === "number" && status >= 500);
}

/**
 * 답 기록 큐. 문항을 풀 때마다 enqueue 하면 한 번에 하나씩, 고른 순서대로 보낸다.
 * 화면은 기록을 기다리지 않는다 (해설은 이미 로컬에서 보여 준다). 끝낼 때만 flush 로 비워질 때까지 기다린다.
 *
 * @param {{
 *   send: (item: {questionId: number, choiceIndex: number}) => Promise<any>,
 *   sleep?: (ms: number) => Promise<void>,
 *   retryDelaysMs?: number[],
 *   onRecorded?: (result: any) => void,
 *   onChange?: (state: {pending: number, failed: number}) => void,
 * }} opts
 */
export function createAnswerRecorder({
  send,
  sleep = defaultSleep,
  retryDelaysMs = DEFAULT_RETRY_DELAYS_MS,
  onRecorded = () => {},
  onChange = () => {},
}) {
  /** @type {Array<{questionId: number, choiceIndex: number}>} 보내야 할 답 (맨 앞이 전송 중) */
  const queue = [];
  /** @type {Array<{questionId: number, choiceIndex: number, error: any}>} */
  let failed = [];
  const seen = new Set();
  /** @type {Promise<void>|null} */
  let running = null;

  const notify = () => onChange({ pending: queue.length, failed: failed.length });

  /** 한 문항을 보낸다. 성공하면 null, 실패하면 마지막 오류를 돌려준다. */
  async function attempt(item) {
    for (let tries = 0; ; tries += 1) {
      try {
        onRecorded(await send(item));
        return null;
      } catch (error) {
        if (!isRetryable(error) || tries >= retryDelaysMs.length) return error;
        await sleep(retryDelaysMs[tries]);
      }
    }
  }

  async function drain() {
    while (queue.length > 0) {
      const item = queue[0];
      const error = await attempt(item);
      queue.shift();
      if (error) failed.push({ ...item, error });
      notify();
    }
  }

  function start() {
    if (running) return;
    running = drain().finally(() => {
      running = null;
      notify();
    });
  }

  return {
    /** 답을 큐에 넣는다. 같은 문항은 한 번만 넣는다. */
    enqueue(questionId, choiceIndex) {
      if (seen.has(questionId)) return;
      seen.add(questionId);
      queue.push({ questionId, choiceIndex });
      notify();
      start();
    },
    /** 큐가 빌 때까지 기다린다. 실패한 답은 failed 에 남고, 기다림은 끝난다. */
    async flush() {
      while (running) await running;
    },
    /** 실패로 분리된 답을 다시 큐에 넣어 보낸다 (네트워크가 돌아온 뒤 등). */
    retryFailed() {
      if (failed.length === 0) return;
      for (const { questionId, choiceIndex } of failed) queue.push({ questionId, choiceIndex });
      failed = [];
      notify();
      start();
    },
    /** 보낼 답도 실패한 답도 없는가. 아니면 아직 저장되지 않은 답이 있다. */
    isIdle() {
      return queue.length === 0 && failed.length === 0;
    },
    get failed() {
      return failed.map((item) => ({ ...item }));
    },
  };
}
