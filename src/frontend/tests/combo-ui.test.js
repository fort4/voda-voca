/*
 * 2026-11-05 - voda-voca - 콤보 UI 테스트: 뱃지 줄 고정 높이·바운스·reduced-motion CSS, 화면 배선(사운드 큐 정책·완료 팡파레·뱃지), 효과음 토글 아이콘, 용어 통일 (v2.2)
 * 파일 위치: src/frontend/tests/combo-ui.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { comboBadgeClass } from "../js/views/components/combo-badge.js";
import { completeCopy } from "../js/core/session-view-model.js";

const ROOT = new URL("..", import.meta.url).pathname;
const read = (path) => readFileSync(join(ROOT, path), "utf8");
const css = read("css/app.css");
const session = read("js/views/study-session-view.js");

/** @param {string} dir @returns {string[]} */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

// ---------- 뱃지 클래스 계산 (DOM 없이) ----------

test("comboBadgeClass: 기본 → combo-badge, 바운스 → is-bounce, 마일스톤 → combo-badge--milestone", () => {
  assert.equal(comboBadgeClass({ visible: true, bounce: false, milestone: false, label: "2콤보" }), "combo-badge");
  assert.equal(comboBadgeClass({ visible: true, bounce: true, milestone: false, label: "3콤보" }), "combo-badge is-bounce");
  assert.equal(comboBadgeClass({ visible: true, bounce: true, milestone: true, label: "5콤보" }), "combo-badge combo-badge--milestone is-bounce");
});

// ---------- CSS ----------

test(".combo-row: 뱃지가 없어도 높이를 차지해 나타날 때 카드가 밀리지 않는다 (레이아웃 시프트 방지)", () => {
  const rule = css.match(/\n\.combo-row\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(rule, /height:\s*\d+px/);
  assert.match(rule, /display:\s*flex/);
});

test(".combo-badge: 토큰 색만 쓰고, 마일스톤은 더 강한 채움을 쓴다", () => {
  const badge = css.match(/\n\.combo-badge\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.ok(badge.length > 0, ".combo-badge 규칙이 없다");
  assert.doesNotMatch(badge.replace(/var\([^)]*\)/g, ""), /#[0-9a-f]{3,8}\b|rgba?\(/i, "리터럴 색 금지 (다크 모드는 토큰이 따라온다)");
  const milestone = css.match(/\.combo-badge--milestone\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(milestone, /var\(--btn-primary-bg\)/);
  assert.match(milestone, /var\(--on-accent\)/);
});

test("combo-pop: 1 → 1.25 → 1 스케일 바운스, is-bounce 일 때만 재생, reduced-motion 에서는 끈다", () => {
  assert.match(css, /@keyframes combo-pop\s*\{[\s\S]*?scale\(1\.25\)/);
  assert.match(css, /\.combo-badge\.is-bounce\s*\{[^}]*animation:\s*combo-pop/);
  assert.doesNotMatch(css.match(/\n\.combo-badge\s*\{([^}]*)\}/)?.[1] ?? "", /animation/, "기본 상태에서는 애니메이션이 없다");
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.combo-badge\.is-bounce\s*\{[^}]*animation:\s*none/s);
});

// ---------- 컴포넌트 ----------

test("combo-badge.js: 시각 전용(aria-hidden)이라 해설 시트의 낭독과 겹치지 않고, 줄은 항상 그려진다", () => {
  const src = read("js/views/components/combo-badge.js");
  assert.match(src, /class:\s*"combo-row",\s*"aria-hidden":\s*"true"/, "속성으로 실제로 달려 있어야 한다 (주석 언급은 인정하지 않는다)");
  assert.match(src, /combo-row/);
  assert.match(src, /flame/);
});

// ---------- 화면 배선 ----------

test("세션 화면: 효과음은 soundCueFor 정책을 거쳐 playCue 로 낸다 (playCorrect 직접 호출 금지)", () => {
  assert.match(session, /soundCueFor\(/);
  assert.match(session, /playCue\(/);
  assert.doesNotMatch(session, /playCorrect/);
});

test("세션 화면: 답 응답 이벤트에서 모드·정오·콤보로 큐를 정한다", () => {
  assert.match(session, /type:\s*"answer"[^}]*mode:\s*state\.mode[^}]*isCorrect[^}]*count:\s*state\.streak/s);
});

test("세션 화면: 완료 팡파레는 세션당 한 번, 요약(중단 여부·푼 수·정답 수)으로 정한다", () => {
  assert.match(session, /type:\s*"complete"[^}]*aborted[^}]*answered[^}]*correct/s);
  assert.match(session, /completedSessionId/);
  assert.match(session, /PHASE\.SESSION_COMPLETE/);
});

test("세션 화면: 콤보 뱃지 줄을 진행 헤더 아래에 항상 그리고, 직전 렌더 값과 비교해 바운스를 정한다", () => {
  assert.match(session, /renderComboRow\(/);
  assert.match(session, /badgeView\(shownCombo,\s*state\.streak\)/);
  assert.match(session, /shownCombo\s*=\s*state\.streak/);
  assert.match(session, /shownCombo\s*=\s*0/, "새 세션 시작 때 초기화");
  assert.doesNotMatch(session, /\?\s*renderComboRow\(/, "조건부 렌더 금지: 줄은 항상 있어야 한다");
});

// ---------- 효과음 토글 ----------

test("효과음 스위치는 bell-ring / bell-off 를 쓰고 '효과음' 라벨이며, volume-* 는 발음(TTS) 전용으로 남긴다", () => {
  const model = read("js/core/preferences-model.js");
  const modal = read("js/views/preferences-modal.js");
  assert.match(model, /bell-off/);
  assert.match(model, /bell-ring/);
  assert.match(model, /효과음/);
  assert.doesNotMatch(model + modal, /정답 소리/);
  assert.doesNotMatch(model + modal, /volume-/);
  assert.match(modal, /subscribeMute\(/, "다른 곳에서 바뀌어도 스위치가 따라온다");
});

test("세션 진행 헤더에는 음소거 버튼을 따로 두지 않는다 (환경 설정 모달 하나만)", () => {
  assert.doesNotMatch(read("js/views/components/progress-header.js"), /toggleMute|sound-toggle|bell-/);
});

// ---------- 용어 통일 ----------

test("완료 요약은 '최대 콤보' 로 보여 준다", () => {
  const summary = { total: 15, answered: 10, correct: 8, wrong: 2, skipped: 0, unanswered: 5, accuracy: 80, bestStreak: 6, memorizedTerms: [], wrongItems: [], aborted: false };
  const stats = completeCopy(summary).stats;
  assert.deepEqual(stats.find((s) => s.label === "최대 콤보"), { label: "최대 콤보", value: "6콤보" });
  assert.equal(stats.find((s) => s.label === "최고 연속"), undefined);
});

test("화면 문구에 '연속 정답' / '최고 연속' 이 남아 있지 않다 (연속 학습일·일 연속은 다른 개념이라 제외)", () => {
  const offenders = jsFiles(join(ROOT, "js"))
    .filter((f) => !f.endsWith("combo-model.js") && !f.endsWith("session-runner.js")) // 주석 설명은 허용
    .filter((f) => /연속 정답!|"최고 연속"|문제 연속 정답/.test(readFileSync(f, "utf8")))
    .map((f) => f.replace(ROOT, ""));
  assert.deepEqual(offenders, []);
});
