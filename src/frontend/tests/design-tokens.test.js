/*
 * 2026-11-05 - voda-voca - 디자인 토큰·폰트 도입 검사: 타입/간격/반경 토큰, Pretendard 로딩, Tailwind 타입 스케일 등록 (v2.2 DS-1, DS-2)
 * 파일 위치: src/frontend/tests/design-tokens.test.js
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname;
const css = readFileSync(`${ROOT}css/app.css`, "utf8");
const html = readFileSync(`${ROOT}index.html`, "utf8");

/** app.css 의 첫 `:root { ... }` 블록 중 토큰 선언 전체를 이어 붙여 돌려준다. */
function rootBlocks() {
  return [...css.matchAll(/:root\s*\{([^}]*)\}/g)].map((m) => m[1]).join("\n");
}

const TOKENS = [
  "--font-sans",
  "--fs-micro", "--fs-caption", "--fs-body", "--fs-lead", "--fs-heading", "--fs-title", "--fs-display",
  "--lh-tight", "--lh-normal", "--lh-relaxed",
  "--space-1", "--space-2", "--space-3", "--space-4", "--space-5", "--space-6", "--space-8",
  "--radius-sm", "--radius-control", "--radius-card", "--radius-pill",
];

for (const token of TOKENS) {
  test(`:root 에 ${token} 토큰이 정의되어 있다`, () => {
    assert.match(rootBlocks(), new RegExp(`${token}\\s*:`));
  });
}

test("--font-sans 는 Pretendard Variable 로 시작하고 시스템 폰트로 폴백한다", () => {
  const m = rootBlocks().match(/--font-sans\s*:\s*([^;]+);/);
  assert.ok(m, "--font-sans 선언이 없다");
  assert.match(m[1], /^\s*["']?Pretendard Variable["']?/);
  for (const fallback of ["Pretendard", "-apple-system", "system-ui", "sans-serif"]) {
    assert.ok(m[1].includes(fallback), `폴백 체인에 ${fallback} 이(가) 없다`);
  }
});

test("body 는 --font-sans 를 쓰고 한글 단어 단위 줄바꿈을 한다", () => {
  const body = css.match(/\n\}\nbody\s*\{([^}]*)\}/)?.[1] ?? ""; // `html,\nbody {` 공용 블록이 아닌 단독 body 규칙
  assert.match(body, /font-family:\s*var\(--font-sans\)/);
  assert.match(body, /word-break:\s*keep-all/);
});

test("index.html: Pretendard Variable 을 preconnect 와 함께 CDN 에서 불러온다 (swap 서브셋 CSS)", () => {
  assert.match(html, /<link[^>]+rel="preconnect"[^>]+href="https:\/\/cdn\.jsdelivr\.net"/);
  assert.match(html, /<link[^>]+rel="stylesheet"[^>]+pretendard[^>]*variable[^>]*dynamic-subset[^>]*\.css/i);
});

test("index.html: Tailwind 설정에 fontFamily 와 타입 스케일(fontSize)이 등록되어 있다", () => {
  const cfg = html.match(/tailwind\.config\s*=\s*(\{[\s\S]*?\n\s{6}\});/)?.[1] ?? "";
  assert.ok(cfg, "tailwind.config 블록을 찾지 못했다");
  assert.match(cfg, /fontFamily/);
  assert.match(cfg, /var\(--font-sans\)/);
  for (const step of ["micro", "caption", "body", "lead", "heading", "title", "display"]) {
    assert.match(cfg, new RegExp(`\\b${step}\\b`), `fontSize 에 ${step} 단계가 없다`);
  }
});

test("Tailwind 설정 스크립트는 Play CDN 스크립트보다 뒤에 온다", () => {
  assert.ok(html.indexOf("cdn.tailwindcss.com") < html.indexOf("tailwind.config"));
});

// ---------- 3단계: 타입 스케일 치환 ----------

import { readdirSync, statSync } from "node:fs";
import { join } from "node:path";

/** @param {string} dir @returns {string[]} 하위 .js 파일 경로 */
function jsFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? jsFiles(path) : path.endsWith(".js") ? [path] : [];
  });
}

test("화면 코드에 text-[NNpx] 같은 임의 글자 크기가 없다 (타입 스케일 토큰 사용)", () => {
  const offenders = [];
  for (const file of jsFiles(join(ROOT, "js"))) {
    const found = readFileSync(file, "utf8").match(/text-\[[\d.]+(?:px|rem)\]/g);
    if (found) offenders.push(`${file.replace(ROOT, "")}: ${[...new Set(found)].join(", ")}`);
  }
  assert.deepEqual(offenders, [], "text-micro/caption/body/lead/heading/title/display 로 바꿔라");
});

test("학습 세션 CSS 의 글자 크기는 타입 스케일 토큰을 쓴다", () => {
  const expectations = [
    [".session-term", "--fs-display"],
    [".session-context", "--fs-lead"],
    [".session-hint", "--fs-micro"],
    [".progress-count", "--fs-caption"],
    [".stat-value", "--fs-heading"],
    [".stat-label", "--fs-micro"],
  ];
  for (const [selector, token] of expectations) {
    const rule = css.match(new RegExp(`\\n${selector.replace(".", "\\.")}\\s*\\{([^}]*)\\}`))?.[1] ?? "";
    assert.match(rule, new RegExp(`font-size:\\s*var\\(${token}\\)`), `${selector} 은 ${token} 을 써야 한다`);
  }
});

// ---------- 4단계: 컴포넌트 ----------

import { buttonClass } from "../js/core/dom.js";

test("CSS 에 .btn, .card, .chip 컴포넌트 기본 클래스가 정의되어 있다", () => {
  for (const cls of [".btn", ".btn-primary", ".btn-secondary", ".btn-danger", ".btn-ghost", ".btn-danger-soft", ".btn-full", ".card", ".card-interactive", ".chip", ".chip-sm"]) {
    assert.ok(new RegExp(`(^|[\\s,])${cls.replace(".", "\\.")}(?![\\w-])`, "m").test(css), `${cls} 정의가 없다`);
  }
});

test(".btn 은 44px 터치 타깃을 보장하고 눌림(3D pressed) 상호작용을 가진다", () => {
  const base = css.match(/\n\.btn\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(base, /min-height:\s*44px/);
  assert.match(base, /min-width:\s*44px/);
  assert.match(base, /box-shadow:\s*0 3px 0 var\(--btn-edge\)/);
  const active = css.match(/\.btn:active:not\(:disabled\)\s*\{([^}]*)\}/)?.[1] ?? "";
  assert.match(active, /translateY\(2px\)/);
});

test("buttonClass: 기존 variant 이름을 모두 .btn 규격으로 돌려준다 (button() 시그니처 호환)", () => {
  for (const variant of ["primary", "secondary", "danger", "ghost", "danger-soft"]) {
    const cls = buttonClass({ variant });
    assert.match(cls, /(^| )btn( |$)/);
    assert.ok(cls.split(" ").includes(`btn-${variant}`), `${variant} 클래스가 없다: ${cls}`);
    assert.ok(cls.split(" ").includes("focus-ring"));
  }
  assert.ok(buttonClass({}).split(" ").includes("btn-primary"), "variant 기본값은 primary");
  assert.ok(buttonClass({ variant: "없는값" }).split(" ").includes("btn-primary"), "알 수 없는 variant 는 primary");
  assert.ok(buttonClass({ full: true }).split(" ").includes("btn-full"));
  assert.ok(!buttonClass({}).split(" ").includes("btn-full"));
});

test("button() 외 파일에 인라인 primary 버튼 스타일(bg-indigo-600 + min-h) 이 남아 있지 않다", () => {
  const offenders = jsFiles(join(ROOT, "js"))
    .filter((f) => !f.endsWith("core/dom.js"))
    .filter((f) => /h\("button"[^\n]*bg-indigo-600/.test(readFileSync(f, "utf8")))
    .map((f) => f.replace(ROOT, ""));
  assert.deepEqual(offenders, [], ".chip 또는 button() 헬퍼를 써라");
});

// ---------- 대비 (WCAG AA) ----------

/** @param {string} hex #rrggbb @returns {number} 상대 휘도 */
function luminance(hex) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
/** @returns {number} 두 색의 대비 비율 */
function contrast(a, b) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}
/** 다크(html.dark) 블록 또는 라이트(:root) 블록에서 색 토큰 값을 읽는다. */
function tokenValue(scope, token) {
  const blocks = scope === "dark" ? [...css.matchAll(/html\.dark\s*\{([^}]*)\}/g)] : [...css.matchAll(/:root\s*\{([^}]*)\}/g)];
  for (const m of blocks.reverse()) {
    const v = m[1].match(new RegExp(`${token}\\s*:\\s*(#[0-9a-fA-F]{6})`));
    if (v) return v[1];
  }
  throw new Error(`${scope} 에서 ${token} 을 찾지 못했다`);
}

for (const scope of ["light", "dark"]) {
  for (const [bgToken, label] of [["--btn-primary-bg", "primary"], ["--btn-danger-bg", "danger"]]) {
    test(`${scope} ${label} 버튼: 글자(--on-accent)와 배경의 대비가 WCAG AA 4.5:1 이상이다`, () => {
      const fg = tokenValue("light", "--on-accent");
      assert.ok(contrast(fg, tokenValue(scope, bgToken)) >= 4.5, `${scope} ${bgToken} 대비 ${contrast(fg, tokenValue(scope, bgToken)).toFixed(2)}:1`);
    });
  }
}

// ---------- 5단계: 위계와 반응형 여백 (sm: 640px+) ----------

import { cardActionVariants } from "../js/core/explore-model.js";

/** @returns {string} `@media (min-width: 640px)` 블록 본문 (중괄호 균형으로 추출) */
function smBlock() {
  const start = css.indexOf("@media (min-width: 640px)");
  if (start < 0) return "";
  let depth = 0;
  for (let i = css.indexOf("{", start); i < css.length; i++) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}" && --depth === 0) return css.slice(css.indexOf("{", start) + 1, i);
  }
  return "";
}

test("모바일 기본 여백 토큰이 있고, 640px 이상에서 한 단계 확장된다", () => {
  for (const token of ["--page-px", "--page-pt", "--stack-gap", "--card-pad"]) {
    assert.match(rootBlocks(), new RegExp(`${token}\\s*:`), `${token} 기본값(모바일)이 없다`);
    assert.match(smBlock(), new RegExp(`${token}\\s*:`), `${token} 의 640px+ 값이 없다`);
  }
  assert.match(smBlock(), /--fs-display\s*:/, "학습 단어(display)는 넓은 화면에서 한 단계 키운다");
});

test(".page, .page-x, .stack, .btn-lg, .kbd-hint 가 정의되어 있고 토큰을 쓴다", () => {
  assert.match(css, /\n\.page\s*\{[^}]*var\(--page-pt\)/);
  assert.match(css, /\n\.page-x\s*\{[^}]*var\(--page-px\)/);
  assert.match(css, /\.stack\s*>\s*\*\s*\+\s*\*\s*\{[^}]*var\(--stack-gap\)/);
  assert.match(css, /\n\.btn-lg\s*\{[^}]*min-height:\s*56px/);
  assert.match(css, /\.card\s*\{[^}]*padding:\s*var\(--card-pad\)/);
});

test("앱 셸은 .page / .page-x 를 쓰고 고정 px-4 여백을 직접 쓰지 않는다", () => {
  assert.match(html, /<main id="app" class="[^"]*\bpage\b/);
  assert.doesNotMatch(html, /<main id="app" class="[^"]*\bpx-4\b/);
  assert.match(html, /max-w-screen-md[^"]*\bpage-x\b/);
});

test("화면 최상위 래퍼는 .stack 을 쓴다 (홈, 탐색, 복습함, 통계)", () => {
  for (const file of ["home-view.js", "explore-view.js", "review-view.js", "stats-view.js"]) {
    assert.match(readFileSync(`${ROOT}js/views/${file}`, "utf8"), /"stack pb-4"/, `${file} 최상위가 .stack 이 아니다`);
  }
});

test("뷰의 카드는 surface + p-N 조합 대신 .card 를 쓴다 (여백이 반응형 토큰을 따르도록)", () => {
  const offenders = jsFiles(join(ROOT, "js/views"))
    .filter((f) => !f.endsWith("word-sheet.js") && !f.endsWith("login.js") && !f.endsWith("signup.js"))
    .filter((f) => /"[^"]*\bsurface\b[^"]*\bp-[45]\b[^"]*"/.test(readFileSync(f, "utf8")))
    .map((f) => f.replace(ROOT, ""));
  assert.deepEqual(offenders, []);
});

test("buttonClass: size=lg 는 .btn-lg 를 붙이고, 홈 CTA 에는 인라인 min-height 가 없다", () => {
  assert.ok(buttonClass({ size: "lg" }).split(" ").includes("btn-lg"));
  assert.ok(!buttonClass({}).split(" ").includes("btn-lg"));
  assert.doesNotMatch(readFileSync(`${ROOT}js/views/home-view.js`, "utf8"), /style:\s*"min-height/);
});

test("탐색 카드: 한 화면에 primary 버튼은 학습 중인 단어장의 '홈에서 학습' 하나뿐이다", () => {
  assert.deepEqual(cardActionVariants({ isActive: false }), { preview: "ghost", main: "secondary" });
  assert.deepEqual(cardActionVariants({ isActive: true }), { preview: "ghost", main: "primary" });
});

test("줄바꿈: 한글을 글자 단위로 쪼개는 word-break: break-word 를 쓰지 않는다 (keep-all 유지)", () => {
  assert.doesNotMatch(css, /word-break:\s*break-word/);
  assert.match(css, /\.session-context\s*\{[^}]*overflow-wrap:\s*anywhere/);
});

test("단축키 안내(.kbd-hint)는 터치 기기(hover: none)에서 숨기고, 뷰는 키 안내를 .kbd-hint 로 감싼다", () => {
  assert.match(css, /@media \(hover: none\)\s*\{[^}]*\.kbd-hint\s*\{[^}]*display:\s*none/);
  assert.match(readFileSync(`${ROOT}js/views/components/feedback-sheet.js`, "utf8"), /kbd-hint|kbdHint/);
  const session = readFileSync(`${ROOT}js/views/study-session-view.js`, "utf8");
  assert.doesNotMatch(session, /"헷갈려요 \(←\)"|"알아요 \(→\)"/, "화살표 안내가 버튼 글자에 박혀 있다");
});

test("640px+ 에서 덮어쓰는 컴포넌트 규칙은 기본 규칙보다 뒤에 있다 (같은 우선순위에서는 나중 규칙이 이긴다)", () => {
  const base = css.indexOf("\n.session-card {");
  const wide = css.indexOf(".session-card { padding: 40px 32px; }");
  assert.ok(base >= 0 && wide > base, ".session-card 의 sm 규칙이 기본 규칙보다 앞에 있어 적용되지 않는다");
});
