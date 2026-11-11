/*
 * 2026-11-05 - voda-voca - 발음 버튼 UI 테스트: 재생 상태→표시 모델, 구독 자동 해제, 44px·다크·reduced-motion CSS, 화면 배선(정지 시점·안내 연결) (v2.2 TTS)
 * 파일 위치: src/frontend/tests/speak-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { bindSpeakState, speakAriaLabel, speakButtonState } from "../js/core/speak-model.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const css = read("css/app.css");

/** @param {string} dir @returns {string[]} */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

// ---------- 표시 모델 ----------

test("speakButtonState: 같은 key 가 재생 중일 때만 playing", () => {
  assert.deepEqual(speakButtonState({ status: "speaking", key: "word:a" }, "word:a"), { playing: true, ariaPressed: "true" });
  assert.deepEqual(speakButtonState({ status: "speaking", key: "word:b" }, "word:a"), { playing: false, ariaPressed: "false" });
  assert.deepEqual(speakButtonState({ status: "idle", key: null }, "word:a"), { playing: false, ariaPressed: "false" });
});

test("speakButtonState: key 가 없는 버튼은 재생 중 표시를 받지 않는다 (key 없는 speak 와 우연히 일치 방지)", () => {
  assert.equal(speakButtonState({ status: "speaking", key: null }, null).playing, false);
  assert.equal(speakButtonState({ status: "speaking", key: null }, undefined).playing, false);
});

test("speakAriaLabel: 단어는 '<단어> 발음 듣기', 예문은 '예문 듣기'", () => {
  assert.equal(speakAriaLabel("word", "apple"), "apple 발음 듣기");
  assert.equal(speakAriaLabel("sentence", "I ate an apple."), "예문 듣기");
});

// ---------- 구독 바인딩 ----------

function fakeBus(initial = { status: "idle", key: null }) {
  let state = initial;
  const listeners = new Set();
  return {
    subscribe: (fn) => { listeners.add(fn); return () => listeners.delete(fn); },
    getState: () => state,
    emit: (next) => { state = next; for (const fn of [...listeners]) fn(next); },
    count: () => listeners.size,
  };
}

test("bindSpeakState: 생성 즉시 현재 상태를 반영하고, 이후 통지를 따라간다", () => {
  const bus = fakeBus({ status: "speaking", key: "k" }); // 화면이 다시 그려진 시점에 이미 재생 중
  const applied = [];
  bindSpeakState({ ...bus, key: "k", isConnected: () => true, apply: (v) => applied.push(v.playing) });
  bus.emit({ status: "idle", key: null });
  bus.emit({ status: "speaking", key: "k" });
  assert.deepEqual(applied, [true, false, true]);
});

test("bindSpeakState: dispose 하면 구독이 풀리고, 두 번 불러도 안전하다", () => {
  const bus = fakeBus();
  const dispose = bindSpeakState({ ...bus, key: "k", isConnected: () => true, apply: () => {} });
  assert.equal(bus.count(), 1);
  dispose();
  dispose();
  assert.equal(bus.count(), 0);
});

test("bindSpeakState: 알림 시점에 DOM 에서 떨어져 있으면 구독을 푼다 (다시 그려져 버려진 버튼의 누수 방지)", () => {
  const bus = fakeBus();
  let connected = true;
  const applied = [];
  bindSpeakState({ ...bus, key: "k", isConnected: () => connected, apply: (v) => applied.push(v.playing) });

  bus.emit({ status: "speaking", key: "k" });
  assert.equal(bus.count(), 1, "붙어 있는 동안은 유지");

  connected = false; // 화면이 다시 그려져 이 버튼이 버려졌다
  bus.emit({ status: "idle", key: null });
  assert.equal(bus.count(), 0, "떨어진 뒤 첫 알림에서 해제");
  const before = applied.length;
  bus.emit({ status: "speaking", key: "k" });
  assert.equal(applied.length, before, "해제 후에는 더 이상 갱신하지 않는다");
});

test("bindSpeakState: 한 번도 알림을 받지 못하고 버려진 버튼도 첫 알림에서 정리된다 (렌더가 반복돼도 구독이 쌓이지 않는다)", () => {
  const bus = fakeBus();
  for (let render = 0; render < 20; render += 1) {
    bindSpeakState({ ...bus, key: "k", isConnected: () => false, apply: () => {} }); // 만들자마자 다음 렌더에서 버려짐
  }
  assert.equal(bus.count(), 20);
  bus.emit({ status: "speaking", key: "k" });
  assert.equal(bus.count(), 0, "알림 한 번에 모두 정리");
});

// ---------- CSS ----------

test(".btn-icon: 44×44px 정사각 아이콘 버튼 (REQ-114)", () => {
  const rule = css.match(/\n\.btn-icon\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(rule, /width:\s*44px/);
  assert.match(rule, /height:\s*44px/);
  assert.match(rule, /padding:\s*0/);
});

test(".speak-btn.is-playing: 강조색 토큰과 아이콘 맥동, reduced-motion 에서는 애니메이션을 끈다", () => {
  const playing = css.match(/\.speak-btn\.is-playing\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(playing, /var\(--accent\)/);
  assert.match(css, /\.speak-btn\.is-playing\s+svg\s*\{[^}]*animation:\s*speak-pulse/);
  assert.match(css, /@keyframes speak-pulse/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.speak-btn\.is-playing\s+svg\s*\{[^}]*animation:\s*none/);
});

// ---------- 화면 배선 ----------

test("화면 코드는 speak/speakWord/speakSentence 를 직접 부르지 않고 speakButton 만 쓴다", () => {
  const offenders = jsFiles(join(ROOT, "js/views"))
    .filter((f) => !f.endsWith("components/speak-button.js"))
    .filter((f) => /(?<![\w.])speak(Word|Sentence)?\(/.test(readFileSync(f, "utf8")) || /import \{[^}]*\bspeak(Word|Sentence)?\b[^}]*\} from "[^"]*tts\.js"/.test(readFileSync(f, "utf8")))
    .map((f) => f.replace(ROOT, ""));
  assert.deepEqual(offenders, []);
});

test("speak-button.js: 카드 탭(뒤집기)으로 이벤트가 번지지 않게 막고, 44px .btn-icon 을 쓴다", () => {
  const src = read("js/views/components/speak-button.js");
  assert.match(src, /stopPropagation/);
  assert.match(src, /btn-icon/);
  assert.match(src, /speak-btn/);
  assert.match(src, /aria-pressed/);
});

test("36px 아이콘 버튼(h-9 w-9)이 화면에 남아 있지 않다 (REQ-114)", () => {
  const offenders = jsFiles(join(ROOT, "js")).filter((f) => /\bh-9 w-9\b/.test(readFileSync(f, "utf8"))).map((f) => f.replace(ROOT, ""));
  assert.deepEqual(offenders, []);
});

test("발음 버튼 배치: 세션 헤더(단어), 해설 시트(예문만), 플래시카드 뒷면(예문), 단어 시트(단어만)", () => {
  assert.match(read("js/views/components/progress-header.js"), /speakButton\(/);
  const sheet = read("js/views/components/feedback-sheet.js");
  assert.doesNotMatch(sheet, /kind:\s*"word"/, "단어 듣기는 세션 헤더에 이미 있으므로 해설 시트에는 두지 않는다 (2026-11-10)");
  assert.match(sheet, /speakButton\([^)]*kind:\s*"sentence"/s);
  assert.match(read("js/views/study-session-view.js"), /speakButton\([^)]*kind:\s*"sentence"/s);
  const words = read("js/views/components/word-sheet.js");
  assert.match(words, /speakButton\([^)]*kind:\s*"word"/s);
  assert.doesNotMatch(words, /kind:\s*"sentence"/, "미리보기 시트에는 예문 듣기를 두지 않는다 (2026-11-10)");
});

test("정지 시점: 문항 전환·다음·중단·화면 정리(세션), 시트 닫힘(단어 시트), 라우트 이동·탭 숨김(앱)", () => {
  const session = read("js/views/study-session-view.js");
  assert.match(session, /stopSpeaking\(\)/);
  assert.match(session, /ACTION\.NEXT[^\n]*\n?[^\n]*stopSpeaking|stopSpeaking[^\n]*ACTION\.NEXT|ACTION\.NEXT \|\| action\.type === ACTION\.ABORT/, "다음/중단에서 멈춘다");
  assert.match(session, /return \(\) => \{[\s\S]*stopSpeaking\(\)[\s\S]*driver\.dispose/, "정리 함수에서 멈춘다");
  assert.match(session, /resetSpeechNotice\(\)/, "새 세션마다 안내를 다시 허용한다");
  assert.match(read("js/views/components/word-sheet.js"), /const close = \(\) => \{[\s\S]*?stopSpeaking\(\)/);
  const app = read("js/app.js");
  assert.match(app, /addEventListener\("hashchange"[\s\S]*?stopSpeaking\(\)/);
  assert.match(app, /visibilitychange/);
  assert.match(app, /pagehide/);
});

test("앱 시작 시 재생 불가 안내를 토스트에 연결한다 (setSpeechNotifier + noticeMessage)", () => {
  const app = read("js/app.js");
  assert.match(app, /setSpeechNotifier\(/);
  assert.match(app, /noticeMessage\(/);
});

test("플래시카드 앞면일 때 뒷면(.flip-back)은 inert 로 두어 보이지 않는 발음 버튼이 탭 순서에 끼지 않는다", () => {
  const src = read("js/views/study-session-view.js");
  assert.match(src, /\.flip-back"\)\.inert\s*=\s*!\(flipped && !preview\)/, "처음 그릴 때");
  assert.match(src, /back\.inert\s*=\s*!flipped/, "뒤집을 때");
});
