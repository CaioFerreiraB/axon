/*
 * Desenhista dos gráficos da conversa (spec 008 FR-005c, ADR-052). Roda no iframe `srcdoc` do Open WebUI, sem
 * `allow-same-origin`, depois do ECharts e do locale pt-BR servidos pela plataforma.
 *
 * Lê a especificação do `<script type="application/json" id="axon-chart">` que a API escreveu — dados de um esquema
 * fechado — e aplica as cores do tema do sistema. Todo texto da especificação vai ao DOM por `textContent` ou pelo
 * `esc()` da dica; os formatadores são deste arquivo, nunca da especificação.
 */
(function () {
  "use strict";

  var source = document.getElementById("axon-chart");
  var plot = document.getElementById("plot");
  if (!source || !plot) return;
  var spec = JSON.parse(source.textContent);

  plot.style.height = spec.height + "px";
  document.getElementById("t").textContent = spec.title;
  var sub = document.getElementById("s");
  if (spec.subtitle) sub.textContent = spec.subtitle;
  else sub.remove();
  plot.setAttribute("aria-label", spec.title + ". Os dados estão na tabela da resposta.");

  function post() {
    var height = Math.ceil(document.documentElement.getBoundingClientRect().height);
    parent.postMessage({ type: "iframe:height", height: height }, "*");
  }

  if (!window.echarts) {
    plot.style.height = "auto";
    plot.textContent = "O gráfico não carregou; os dados estão na tabela da resposta.";
    post();
    return;
  }

  var number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });
  var compact = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
  var percent = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
  var day = new Intl.DateTimeFormat("pt-BR", { day: "numeric", month: "short", year: "numeric" });
  var dayTime = new Intl.DateTimeFormat("pt-BR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  // Pilha explícita: `inherit` vira uma regra `font` inválida no texto rico do eixo de datas, que o navegador descarta.
  var FONT = '"Mona Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif';
  var ENTITIES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return ENTITIES[c];
    });
  }

  function withUnit(text) {
    if (!spec.unit) return text;
    return spec.prefix ? spec.unit + " " + text : text + " " + spec.unit;
  }

  function value(v) {
    if (Array.isArray(v)) v = v[1];
    return typeof v === "number" ? withUnit(number.format(v)) : "—";
  }

  function when(v) {
    var date = new Date(v);
    if (isNaN(date)) return String(v);
    return (date.getHours() || date.getMinutes() ? dayTime : day).format(date);
  }

  // Eixo de datas com rótulos de um tamanho só: o ano no 1º de janeiro, o mês no dia 1, senão dia e mês.
  var monthName = new Intl.DateTimeFormat("pt-BR", { month: "short" });
  function month(date) {
    return monthName.format(date).replace(".", "");
  }
  function tick(v) {
    var date = new Date(v);
    if (date.getDate() === 1 && date.getMonth() === 0) return String(date.getFullYear());
    return date.getDate() === 1 ? month(date) : date.getDate() + " " + month(date);
  }

  function heading(p) {
    var v = p.axisValue !== undefined ? p.axisValue : Array.isArray(p.value) ? p.value[0] : p.name;
    if (spec.temporal) return when(v);
    return typeof v === "number" ? number.format(v) : String(v);
  }

  // Valor em destaque e nome em segundo plano; a série identificada por um traço da cor dela.
  function row(p, theme, label) {
    return (
      '<div style="display:flex;align-items:center;gap:8px;margin-top:4px">' +
      '<span style="display:inline-block;width:10px;height:2px;border-radius:1px;background:' +
      esc(p.color) +
      '"></span><span style="color:' +
      theme.text2 +
      '">' +
      esc(label) +
      '</span><b style="margin-left:auto;padding-left:16px;color:' +
      theme.text +
      '">' +
      esc(value(p.value)) +
      "</b></div>"
    );
  }

  function caption(text, theme) {
    return '<div style="color:' + theme.text3 + '">' + esc(text) + "</div>";
  }

  function tooltip(theme) {
    var body = tooltipBody(theme);
    return function (params) {
      return '<div style="font-size:12px;line-height:1.4">' + body(params) + "</div>";
    };
  }

  function tooltipBody(theme) {
    return function (params) {
      if (!Array.isArray(params)) {
        if (params.seriesType === "pie") {
          return (
            caption(params.seriesName, theme) +
            row(params, theme, params.name) +
            caption(percent.format(params.percent) + "%", theme)
          );
        }
        return caption(heading(params), theme) + row(params, theme, params.seriesName);
      }
      if (!params.length) return "";
      return (
        caption(heading(params[0]), theme) +
        params
          .map(function (p) {
            return row(p, theme, p.seriesName);
          })
          .join("")
      );
    };
  }

  function axisLabels(axis, theme) {
    var labels = { color: theme.text3, fontSize: 11, fontFamily: FONT, hideOverlap: true };
    if (axis.type === "value") {
      labels.formatter = function (v) {
        return compact.format(v);
      };
    }
    if (axis.type === "time") {
      labels.formatter = tick;
      labels.rich = { primary: { fontSize: 11, fontWeight: "normal", fontFamily: FONT, color: theme.text3 } };
    }
    return Object.assign(
      {
        axisLine: { lineStyle: { color: theme.grid } },
        axisTick: { show: false },
        splitLine: { show: axis.type === "value", lineStyle: { color: theme.grid, type: "solid" } },
        nameTextStyle: { color: theme.text3, fontSize: 11 },
      },
      axis,
      { axisLabel: labels }
    );
  }

  function themed(theme) {
    var option = JSON.parse(JSON.stringify(spec.option));
    option.backgroundColor = "transparent";
    option.color = theme.series;
    option.animationDuration = 500;
    option.textStyle = { fontFamily: FONT, color: theme.text2 };
    option.tooltip = Object.assign(option.tooltip || {}, {
      confine: true,
      formatter: tooltip(theme),
      backgroundColor: theme.tooltip,
      borderColor: theme.border,
      padding: [8, 10],
      textStyle: { color: theme.text, fontSize: 12, fontFamily: FONT },
      extraCssText: "border-radius:8px;box-shadow:0 8px 24px -6px rgb(0 0 0 / .18)",
    });
    if (option.tooltip.trigger === "axis") {
      option.tooltip.axisPointer = { type: "line", lineStyle: { color: theme.border, width: 1, type: "solid" } };
    }
    if (option.legend) {
      option.legend.textStyle = { color: theme.text2 };
      option.legend.inactiveColor = theme.grid;
      option.legend.pageTextStyle = { color: theme.text3 };
    }
    if (option.xAxis) option.xAxis = axisLabels(option.xAxis, theme);
    if (option.yAxis) option.yAxis = axisLabels(option.yAxis, theme);
    (option.series || []).forEach(function (s) {
      if (s.type === "pie") {
        s.itemStyle = Object.assign({}, s.itemStyle, { borderColor: theme.surface });
        s.label = Object.assign({}, s.label, {
          color: theme.text2,
          formatter: function (p) {
            return p.name + "  " + percent.format(p.percent) + "%";
          },
        });
        s.labelLine = { lineStyle: { color: theme.border } };
      }
      if (s.type === "bar" && s.stack) s.itemStyle = Object.assign({}, s.itemStyle, { borderColor: theme.surface });
      if (s.type === "scatter") s.itemStyle = { borderColor: theme.surface, borderWidth: 2 };
      if (s.endLabel) s.endLabel = Object.assign({}, s.endLabel, { color: theme.text2, fontSize: 11 });
    });
    (option.dataZoom || []).forEach(function (z) {
      if (z.type !== "slider") return;
      z.borderColor = theme.grid;
      z.textStyle = { color: theme.text3 };
      z.fillerColor = "rgba(42,120,214,.12)";
      z.handleStyle = { color: theme.surface, borderColor: theme.border };
      z.dataBackground = { lineStyle: { color: theme.border }, areaStyle: { color: theme.grid } };
      z.labelFormatter = function (v) {
        return spec.temporal ? when(v) : number.format(v);
      };
    });
    return option;
  }

  var dark = window.matchMedia("(prefers-color-scheme: dark)");
  var chart = null;

  function render() {
    if (chart) chart.dispose();
    chart = echarts.init(plot, null, { renderer: "svg", locale: "PT-br" });
    chart.setOption(themed(dark.matches ? spec.themes.dark : spec.themes.light));
  }

  render();
  if (dark.addEventListener) dark.addEventListener("change", render);
  new ResizeObserver(function () {
    if (chart) chart.resize();
    post();
  }).observe(document.body);
  post();
})();
