/*
 * 2026-11-26 - voda-voca - 통계 차트 설정: CSS 토큰에서 팔레트를 읽어 Chart.js 설정(회차별·날짜별 정답률, 최근 7일 활동)을 만든다 (DOM 없는 순수 로직, REQ-132, REQ-155)
 * 파일 위치: src/frontend/js/core/chart-model.js
 */

const PALETTE_TOKENS = Object.freeze({
  sessions: "--chart-sessions",
  daily: "--chart-daily",
  weekly: "--chart-weekly",
  text: "--text",
  muted: "--muted",
  grid: "--border",
  surface: "--surface",
  tooltipBg: "--control",
  tooltipBorder: "--border-strong",
  font: "--font-sans",
});

/** @param {(token: string) => string} read CSS 변수 값을 돌려주는 함수 */
export function readChartPalette(read) {
  return Object.fromEntries(Object.entries(PALETTE_TOKENS).map(([key, token]) => [key, read(token).trim()]));
}

/** @param {string} hex #rrggbb @param {number} alpha */
export function withAlpha(hex, alpha) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/**
 * 위에서 아래로 옅어지는 채움. Chart.js 는 첫 계산 때 차트 영역을 아직 모르므로 그때는 단색을 쓴다.
 * @param {string} color #rrggbb
 * @param {number} top 위쪽 불투명도
 * @param {number} bottom 아래쪽 불투명도
 */
export function verticalGradient(color, top, bottom) {
  return ({ chart }) => {
    const area = chart.chartArea;
    if (!area) return withAlpha(color, top);
    const gradient = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradient.addColorStop(0, withAlpha(color, top));
    gradient.addColorStop(1, withAlpha(color, bottom));
    return gradient;
  };
}

/**
 * 키보드로 값 사이를 옮겨 다닐 때의 다음 위치. 다루지 않는 키면 null.
 * @param {number} current @param {string} key @param {number} length
 * @returns {number|null}
 */
export function nextIndex(current, key, length) {
  if (length === 0) return null;
  const target = { ArrowLeft: current - 1, ArrowRight: current + 1, Home: 0, End: length - 1 }[key];
  return target === undefined ? null : Math.min(length - 1, Math.max(0, target));
}

const percent = (value) => `${value}%`;

/** 막대와 점이 차례로 올라오는 등장 모션. 첫 그리기에서만 지연을 준다. */
function entrance(animate) {
  if (!animate) return false;
  return {
    duration: 900,
    easing: "easeOutQuart",
    delay: (context) => (context.type === "data" && context.mode === "default" ? context.dataIndex * 40 : 0),
  };
}

/** 세 차트가 함께 쓰는 틀: 범례 없음(계열 1개, 제목이 이름), 옅은 가로 눈금선, 닿기 쉬운 말풍선 */
function baseOptions({ palette, animate, y, tooltip, labels }) {
  const font = { family: palette.font, size: 11, weight: 600 };
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: entrance(animate),
    interaction: { mode: "index", intersect: false },
    layout: { padding: { top: 22, right: 6 } }, // 막대 끝 값 라벨 자리
    scales: {
      x: {
        grid: { display: false },
        border: { color: palette.grid },
        ticks: { color: palette.muted, font, maxRotation: 0, autoSkip: true, autoSkipPadding: 8 },
      },
      y: {
        ...y,
        grid: { color: palette.grid, drawTicks: false },
        border: { display: false },
        ticks: { color: palette.muted, font, padding: 8, ...y.ticks },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: palette.tooltipBg,
        borderColor: palette.tooltipBorder,
        borderWidth: 1,
        titleColor: palette.muted,
        titleFont: { ...font, size: 12 },
        bodyColor: palette.text,
        bodyFont: { ...font, size: 15, weight: 700 },
        footerColor: palette.muted,
        footerFont: { ...font, size: 12 },
        displayColors: false,
        padding: 10,
        cornerRadius: 10,
        callbacks: tooltip,
      },
      vodaValueLabels: { ...labels, color: palette.text, font: `700 12px ${palette.font}` },
    },
  };
}

const accuracyAxis = () => ({ min: 0, max: 100, ticks: { stepSize: 25, callback: percent } });

/**
 * 회차별 정답률: 면적을 채운 선 그래프. 마지막 회차를 크게 찍고 값을 붙인다.
 * @param {Array<{label: string, percent: number, accuracyText: string, scoreText: string, change: string|null}>} sessions
 */
export function sessionChartConfig(sessions, palette, { animate = true } = {}) {
  const last = sessions.length - 1;
  const options = baseOptions({
    palette,
    animate,
    y: accuracyAxis(),
    tooltip: {
      label: ({ dataIndex }) => `정답률 ${sessions[dataIndex].accuracyText}`,
      footer: ([item]) => {
        const s = sessions[item.dataIndex];
        return s.change ? [`${s.scoreText} 정답`, `직전 회차 대비 ${s.change}`] : [`${s.scoreText} 정답`];
      },
    },
    labels: { indices: last >= 0 ? [last] : [], format: percent },
  });
  options.scales.x.offset = sessions.length === 1; // 점 하나가 축 끝에 붙지 않게
  return {
    type: "line",
    data: {
      labels: sessions.map((s) => s.label),
      datasets: [
        {
          data: sessions.map((s) => s.percent),
          borderColor: palette.sessions,
          borderWidth: 3,
          borderCapStyle: "round",
          borderJoinStyle: "round",
          cubicInterpolationMode: "monotone",
          fill: true,
          backgroundColor: verticalGradient(palette.sessions, 0.38, 0.02),
          pointRadius: sessions.map((_, i) => (i === last ? 6 : 4)),
          pointHoverRadius: 8,
          pointHitRadius: 16,
          pointBackgroundColor: palette.sessions,
          pointBorderColor: palette.surface,
          pointBorderWidth: 2,
          pointHoverBorderWidth: 3,
          pointHoverBackgroundColor: palette.sessions,
          pointHoverBorderColor: palette.surface,
          clip: false,
        },
      ],
    },
    options,
  };
}

/** 막대 공통 모양: 24px 이하, 데이터 쪽 끝만 둥글게 */
const bar = (data) => ({ data, maxBarThickness: 24, borderRadius: 4, borderSkipped: "start", categoryPercentage: 0.8, barPercentage: 0.9 });

/**
 * 날짜별 정답률: 세로 막대. 0% 인 날도 "풀었지만 모두 틀림" 이 보이도록 흔적을 남긴다.
 * @param {Array<{label: string, percent: number, accuracyText: string, text: string}>} daily
 */
export function dailyChartConfig(daily, palette, { animate = true } = {}) {
  const last = daily.length - 1;
  return {
    type: "bar",
    data: {
      labels: daily.map((d) => d.label),
      datasets: [
        {
          ...bar(daily.map((d) => d.percent)),
          minBarLength: 3,
          backgroundColor: verticalGradient(palette.daily, 1, 0.45),
          hoverBackgroundColor: palette.daily,
        },
      ],
    },
    options: baseOptions({
      palette,
      animate,
      y: accuracyAxis(),
      tooltip: {
        label: ({ dataIndex }) => `정답률 ${daily[dataIndex].accuracyText}`,
        footer: ([item]) => daily[item.dataIndex].text,
      },
      labels: { indices: last >= 0 ? [last] : [], format: percent },
    }),
  };
}

/**
 * 최근 7일 학습 단어 수: 오늘 막대는 진하게, 지난 날은 옅게. 값은 가장 많은 날과 오늘에만 붙인다.
 * @param {Array<{label: string, count: number, isToday: boolean}>} weekly
 */
export function weeklyChartConfig(weekly, palette, { animate = true } = {}) {
  const today = verticalGradient(palette.weekly, 1, 0.9);
  const past = verticalGradient(palette.weekly, 0.72, 0.42);
  const peak = Math.max(0, ...weekly.map((d) => d.count));
  const labelled = weekly.flatMap((d, i) => (d.count > 0 && (d.isToday || d.count === peak) ? [i] : []));
  return {
    type: "bar",
    data: {
      labels: weekly.map((d) => (d.isToday ? [d.label, "오늘"] : d.label)),
      datasets: [
        {
          ...bar(weekly.map((d) => d.count)),
          backgroundColor: (context) => (weekly[context.dataIndex]?.isToday ? today : past)(context),
          hoverBackgroundColor: palette.weekly,
        },
      ],
    },
    options: baseOptions({
      palette,
      animate,
      y: { beginAtZero: true, suggestedMax: 4, ticks: { precision: 0, maxTicksLimit: 5 } },
      tooltip: {
        title: ([item]) => `${weekly[item.dataIndex].label}요일${weekly[item.dataIndex].isToday ? " (오늘)" : ""}`,
        label: ({ dataIndex }) => `${weekly[dataIndex].count}개 단어`,
      },
      labels: { indices: labelled, format: (value) => `${value}개` },
    }),
  };
}

/** 고른 데이터 위에 값을 적는다. 라벨이 차트 좌우 밖으로 잘리지 않게 안쪽으로 당긴다. */
export const valueLabelPlugin = {
  id: "vodaValueLabels",
  afterDatasetsDraw(chart, _args, options) {
    const points = chart.getDatasetMeta(0).data;
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.font = options.font;
    ctx.fillStyle = options.color;
    ctx.textAlign = "center";
    ctx.textBaseline = "bottom";
    for (const index of options.indices ?? []) {
      const point = points[index];
      if (!point) continue;
      const text = options.format(chart.data.datasets[0].data[index]);
      const half = ctx.measureText(text).width / 2;
      const x = Math.min(chart.width - half, Math.max(chartArea.left + half, point.x));
      ctx.fillText(text, x, point.y - 8);
    }
    ctx.restore();
  },
};

/** 가리킨 위치를 지나는 세로 안내선. 선 그래프에서 어느 회차를 읽는지 알려 준다. */
export const crosshairPlugin = {
  id: "vodaCrosshair",
  beforeDatasetsDraw(chart) {
    const [active] = chart.tooltip?.getActiveElements() ?? [];
    if (!active || chart.config.type !== "line") return;
    const { ctx, chartArea } = chart;
    ctx.save();
    ctx.strokeStyle = chart.options.scales.x.border.color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(active.element.x, chartArea.top);
    ctx.lineTo(active.element.x, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  },
};
