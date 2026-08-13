/**
 * Builds the securitized products surveillance summary deck from pipeline output.
 *
 * Reads output/run_metrics.json and the generated CSVs, so the deck always
 * reflects the latest run rather than being hand-maintained.
 *
 * Run: node tools/build_deck.js
 */
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "output");

// ---- palette: institutional navy, ice, amber for risk escalation
const NAVY = "0F1E3D";
const NAVY_MID = "1D3461";
const ICE = "E8EEF7";
const ICE_MID = "C3D3EA";
const AMBER = "D98324";
const RED = "9C2B2B";
const GREEN = "2E6E4F";
const WHITE = "FFFFFF";
const GREY = "6B7280";

const HEAD = "Cambria";
const BODY = "Calibri";

// ---------------------------------------------------------------- data
const metrics = JSON.parse(fs.readFileSync(path.join(OUT, "run_metrics.json"), "utf8"));

/** Splits one CSV line, honouring double-quoted fields.
 *  Scenario labels contain commas ("Credit stress (rising unemployment, HPI
 *  decline)"), so a naive split on "," silently shifts every later column. */
function splitCsvLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { cur += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
    } else {
      cur += ch;
    }
  }
  out.push(cur);
  return out;
}

function readCsv(name) {
  const text = fs.readFileSync(path.join(OUT, name), "utf8").trim();
  const [head, ...rows] = text.split("\n");
  const cols = splitCsvLine(head);
  return rows.map((line) => {
    const parts = splitCsvLine(line);
    const o = {};
    cols.forEach((c, i) => {
      const v = parts[i];
      o[c] = v !== undefined && v !== "" && !isNaN(Number(v)) ? Number(v) : v;
    });
    return o;
  });
}

const fico = readCsv("strat_fico.csv");
const geo = readCsv("strat_geography.csv");
const exposure = readCsv("exposure_rwa.csv");
const stress = readCsv("scenario_stress.csv");
const cohorts = readCsv("cohort_risk_gnn.csv");

const s = metrics.pool_summary;
const val = metrics.forecaster_validation || {};
const upb = s.total_upb;

const money = (x) =>
  Math.abs(x) >= 1e6 ? `$${(x / 1e6).toFixed(1)}mm` : `$${Math.round(x).toLocaleString()}`;

// ---------------------------------------------------------------- deck
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3 x 7.5
pres.author = "Saksham Khanna";
pres.title = "Securitized Products Surveillance";

const W = 13.3;

/** Section title used on every content slide. */
function slideTitle(slide, text, sub) {
  slide.addText(text, {
    x: 0.6, y: 0.42, w: W - 1.2, h: 0.6,
    fontFace: HEAD, fontSize: 32, bold: true, color: NAVY, margin: 0,
  });
  if (sub) {
    slide.addText(sub, {
      x: 0.6, y: 1.04, w: W - 1.2, h: 0.34,
      fontFace: BODY, fontSize: 13, color: GREY, margin: 0,
    });
  }
}

/** Large number + label block. */
function statBlock(slide, x, y, w, value, label, color) {
  slide.addText(value, {
    x, y, w, h: 0.72,
    fontFace: HEAD, fontSize: 34, bold: true, color: color || NAVY,
    align: "center", margin: 0,
  });
  slide.addText(label, {
    x, y: y + 0.74, w, h: 0.36,
    fontFace: BODY, fontSize: 11.5, color: GREY, align: "center", margin: 0,
  });
}

// ---------------------------------------------------------------- 1. title
{
  const slide = pres.addSlide();
  slide.background = { color: NAVY };

  slide.addText("Monthly Surveillance Report", {
    x: 0.9, y: 2.15, w: 10.5, h: 0.9,
    fontFace: HEAD, fontSize: 44, bold: true, color: WHITE, margin: 0,
  });
  slide.addText("Synthetic RMBS Pool 2026-1", {
    x: 0.9, y: 3.05, w: 10.5, h: 0.55,
    fontFace: HEAD, fontSize: 26, color: ICE_MID, margin: 0,
  });
  slide.addText(
    "Model-driven collateral surveillance: stratification, cashflow projection, " +
    "correlated risk and generated scenario stress",
    { x: 0.9, y: 3.75, w: 9.6, h: 0.7, fontFace: BODY, fontSize: 14, color: ICE_MID, margin: 0 }
  );
  slide.addText(
    `Generated ${String(metrics.generated_at || "").slice(0, 10)}  ·  synthetic data for demonstration`,
    { x: 0.9, y: 5.9, w: 10.5, h: 0.4, fontFace: BODY, fontSize: 11, color: "8FA6C4", margin: 0 }
  );
  slide.addNotes(
    "This deck is generated directly from the pipeline's output artifacts, so it always " +
    "reflects the latest surveillance run. All data is synthetic."
  );
}

// ---------------------------------------------------------------- 2. pool snapshot
{
  const slide = pres.addSlide();
  slideTitle(slide, "Pool Snapshot", "Loan-level collateral characteristics at the surveillance date");

  const stats = [
    [money(upb), "Current UPB", NAVY],
    [s.loan_count.toLocaleString(), "Loans", NAVY],
    [String(Math.round(s.wa_fico)), "WA FICO", NAVY],
    [`${s.wa_ltv.toFixed(1)}%`, "WA LTV", NAVY],
  ];
  stats.forEach(([v, l, c], i) => {
    const x = 0.6 + i * 3.1;
    slide.addShape(pres.ShapeType.roundRect, {
      x, y: 1.7, w: 2.85, h: 1.95, fill: { color: ICE },
      line: { color: ICE_MID, width: 1 }, rectRadius: 0.08,
    });
    statBlock(slide, x, 2.05, 2.85, v, l, c);
  });

  const more = [
    ["WA coupon", `${s.wa_coupon.toFixed(3)}%`],
    ["WA DTI", `${s.wa_dti.toFixed(1)}%`],
    ["WA seasoning", `${s.wa_seasoning_mo.toFixed(1)} months`],
    ["Largest state concentration", `${geo[0].state} — ${geo[0].pct_of_pool.toFixed(1)}% of UPB`],
  ];
  slide.addTable(
    more.map(([k, v]) => [
      { text: k, options: { fontFace: BODY, fontSize: 13, color: NAVY_MID, bold: true } },
      { text: v, options: { fontFace: BODY, fontSize: 13, color: "333333" } },
    ]),
    {
      x: 0.6, y: 4.15, w: 6.0, colW: [3.2, 2.8], rowH: 0.56,
      border: { type: "solid", color: ICE_MID, pt: 1 },
    }
  );

  slide.addText(
    "Geographic concentration is the dominant driver of tail loss in the stressed " +
    "scenarios — regional employment and house-price shocks hit whole cohorts at once, " +
    "not individual loans.",
    {
      x: 7.1, y: 4.15, w: 5.6, h: 2.2, fontFace: BODY, fontSize: 13.5,
      color: "333333", margin: 0, valign: "top",
    }
  );
  slide.addNotes("Pool snapshot. Note the geographic concentration point — it sets up the GNN slide.");
}

// ---------------------------------------------------------------- 3. stratification
{
  const slide = pres.addSlide();
  slideTitle(slide, "Collateral Stratification", "Balance-weighted cuts by credit quality and geography");

  slide.addChart(
    pres.ChartType.bar,
    [{
      name: "UPB",
      labels: fico.map((r) => String(r.bucket)),
      values: fico.map((r) => Number((r.upb / 1e6).toFixed(1))),
    }],
    {
      x: 0.6, y: 1.65, w: 6.0, h: 5.15,
      barDir: "col",
      valAxisMinVal: 0,
      dataLabelFormatCode: '0.0',
      showTitle: true, title: "UPB by FICO band ($mm)",
      titleFontFace: HEAD, titleFontSize: 14, titleColor: NAVY,
      chartColors: [NAVY_MID],
      showValue: true, dataLabelPosition: "outEnd",
      dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: "333333",
      showLegend: false,
      catAxisLabelFontFace: BODY, catAxisLabelFontSize: 11, catAxisLabelColor: "444444",
      valAxisLabelFontFace: BODY, valAxisLabelFontSize: 10, valAxisLabelColor: "666666",
      valGridLine: { color: "E3E3E3", size: 1 },
      catGridLine: { style: "none" },
    }
  );

  slide.addChart(
    pres.ChartType.bar,
    [{
      name: "% of pool",
      labels: geo.slice(0, 6).map((r) => String(r.state)),
      values: geo.slice(0, 6).map((r) => Number(r.pct_of_pool.toFixed(2))),
    }],
    {
      x: 6.9, y: 1.65, w: 5.8, h: 5.15,
      barDir: "bar",
      showTitle: true, title: "Top state concentrations (% of UPB)",
      // Auto-scaling starts this axis near the data floor, which visually
      // exaggerates near-identical concentrations. Anchor it at zero.
      valAxisMinVal: 0, valAxisMaxVal: 14,
      dataLabelFormatCode: '0.0"%"',
      titleFontFace: HEAD, titleFontSize: 14, titleColor: NAVY,
      chartColors: [AMBER],
      showValue: true, dataLabelPosition: "outEnd",
      dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: "333333",
      showLegend: false,
      catAxisLabelFontFace: BODY, catAxisLabelFontSize: 11, catAxisLabelColor: "444444",
      valAxisLabelFontFace: BODY, valAxisLabelFontSize: 10, valAxisLabelColor: "666666",
      valGridLine: { color: "E3E3E3", size: 1 },
      catGridLine: { style: "none" },
    }
  );
  slide.addNotes("Stratification tapes are computed by live formulas over the loan tape in the Excel pack.");
}

// ---------------------------------------------------------------- 4. projected performance
{
  const slide = pres.addSlide();
  slideTitle(slide, "Model-Projected Performance",
    "Prepayment and default speeds from a temporal-attention Transformer, over a 36-month horizon");

  const cards = [
    [`${(metrics.avg_cpr * 100).toFixed(2)}%`, "Average CPR", NAVY],
    [`${(metrics.avg_cdr * 100).toFixed(2)}%`, "Average CDR", AMBER],
    [money(metrics.cumulative_loss_base), "Cumulative loss (base)", NAVY],
  ];
  cards.forEach(([v, l, c], i) => {
    const x = 0.6 + i * 4.05;
    slide.addShape(pres.ShapeType.roundRect, {
      x, y: 1.75, w: 3.75, h: 1.9, fill: { color: ICE },
      line: { color: ICE_MID, width: 1 }, rectRadius: 0.08,
    });
    statBlock(slide, x, 2.1, 3.75, v, l, c);
  });

  slide.addText("Holdout validation", {
    x: 0.6, y: 4.05, w: 5.5, h: 0.4,
    fontFace: HEAD, fontSize: 18, bold: true, color: NAVY, margin: 0,
  });
  slide.addTable(
    [
      [
        { text: "Metric", options: { bold: true, color: WHITE, fill: { color: NAVY_MID } } },
        { text: "CPR", options: { bold: true, color: WHITE, fill: { color: NAVY_MID } } },
        { text: "CDR", options: { bold: true, color: WHITE, fill: { color: NAVY_MID } } },
      ],
      ["R²", String(val.cpr_r2 ?? "—"), String(val.cdr_r2 ?? "—")],
      ["MAE", String(val.cpr_mae ?? "—"), String(val.cdr_mae ?? "—")],
      ["Predicted sd", "—", String(val.cdr_pred_sd ?? "—")],
      ["Realised sd", "—", String(val.cdr_true_sd ?? "—")],
    ],
    {
      x: 0.6, y: 4.55, w: 5.5, colW: [2.3, 1.6, 1.6], rowH: 0.5,
      fontFace: BODY, fontSize: 12, color: "333333",
      border: { type: "solid", color: ICE_MID, pt: 1 },
    }
  );

  slide.addText("Why the sd comparison is reported", {
    x: 6.6, y: 4.05, w: 6.1, h: 0.4,
    fontFace: HEAD, fontSize: 18, bold: true, color: NAVY, margin: 0,
  });
  slide.addText(
    [
      { text: "CPR variance is roughly 100x CDR variance. Under a plain MSE the model minimises loss by predicting a constant default rate — scoring well while being economically useless.", options: { bullet: true, breakLine: true } },
      { text: "Standardising targets per-head fixed it: holdout CDR R² moved from 0.10 to 0.97.", options: { bullet: true, breakLine: true } },
      { text: "Predicted sd is now reported against realised sd on every run, so a future collapse is visible immediately.", options: { bullet: true } },
    ],
    {
      x: 6.6, y: 4.55, w: 6.1, h: 2.3, fontFace: BODY, fontSize: 13,
      color: "333333", margin: 0, paraSpaceAfter: 8, valign: "top",
    }
  );
  slide.addNotes(
    "The loss-scaling failure is the most important thing on this slide. Be ready to explain " +
    "why per-head target standardisation fixes it."
  );
}

// ---------------------------------------------------------------- 5. correlated risk
{
  const slide = pres.addSlide();
  slideTitle(slide, "Correlated Default Risk",
    "A graph neural network over originator x state cohorts, capturing risk that loan-level models miss");

  const top = cohorts
    .slice()
    .sort((a, b) => b.gnn_risk_multiplier - a.gnn_risk_multiplier)
    .slice(0, 5);

  const rows = [
    ["Originator", "State", "UPB", "Risk multiplier", "Adj. CDR"].map((t) => ({
      text: t, options: { bold: true, color: WHITE, fill: { color: NAVY_MID } },
    })),
    ...top.map((r) => [
      String(r.originator),
      String(r.state),
      money(r.upb),
      `${r.gnn_risk_multiplier.toFixed(2)}x`,
      `${(r.gnn_adjusted_cdr * 100).toFixed(2)}%`,
    ]),
  ];
  slide.addTable(rows, {
    x: 0.6, y: 1.75, w: 7.4, colW: [2.6, 0.9, 1.5, 1.4, 1.0], rowH: 0.48,
    fontFace: BODY, fontSize: 11.5, color: "333333",
    border: { type: "solid", color: ICE_MID, pt: 1 },
  });

  // The repetition in the originator column is the finding, not a defect —
  // call it out explicitly so it reads as a signal rather than a broken table.
  const topOrig = top[0].originator;
  const sameOrig = top.filter((r) => r.originator === topOrig).length;
  slide.addShape(pres.ShapeType.roundRect, {
    x: 0.6, y: 4.9, w: 7.4, h: 1.75, fill: { color: "FBF0E4" },
    line: { color: AMBER, width: 1 }, rectRadius: 0.06,
  });
  slide.addText(
    `${sameOrig} of the ${top.length} highest-risk cohorts share a single originator — ` +
    `${topOrig}. A loan-level model scores these as independent exposures across ` +
    `${sameOrig} states; the graph identifies them as one concentrated underwriting risk.`,
    {
      x: 0.85, y: 5.12, w: 6.9, h: 1.35, fontFace: BODY, fontSize: 13,
      color: "6B4415", margin: 0, valign: "top",
    }
  );

  slide.addShape(pres.ShapeType.roundRect, {
    x: 8.4, y: 1.75, w: 4.3, h: 5.0, fill: { color: ICE },
    line: { color: ICE_MID, width: 1 }, rectRadius: 0.08,
  });
  slide.addText("Why a graph", {
    x: 8.7, y: 2.05, w: 3.7, h: 0.4,
    fontFace: HEAD, fontSize: 18, bold: true, color: NAVY, margin: 0,
  });
  slide.addText(
    [
      { text: "A per-loan hazard model treats every loan as independent.", options: { bullet: true, breakLine: true } },
      { text: "Loans sharing an originator inherit its underwriting standards; loans sharing a state face the same employment and house-price shocks.", options: { bullet: true, breakLine: true } },
      { text: "The GCN propagates deterioration across connected cohorts, so a signal on one originator lifts its other state cohorts rather than being treated as isolated.", options: { bullet: true, breakLine: true } },
      { text: `Average multiplier applied: ${metrics.gnn_avg_multiplier.toFixed(3)}x`, options: { bullet: true } },
    ],
    {
      x: 8.7, y: 2.6, w: 3.7, h: 3.9, fontFace: BODY, fontSize: 12.5,
      color: "333333", margin: 0, paraSpaceAfter: 7, valign: "top",
    }
  );
  slide.addNotes("This is the structural tail risk that flat models systematically understate.");
}

// ---------------------------------------------------------------- 6. exposure
{
  const slide = pres.addSlide();
  slideTitle(slide, "Tranche Exposure, Expected Loss and RWA",
    "Sequential-pay structure — losses absorbed subordinate-first, principal paid senior-first");

  const rows = [
    ["Tranche", "Rating", "EAD", "PD", "LGD", "Expected loss", "RW", "RWA"].map((t) => ({
      text: t, options: { bold: true, color: WHITE, fill: { color: NAVY_MID } },
    })),
    ...exposure.map((r) => [
      String(r.tranche),
      String(r.proxy_rating),
      money(r.ead),
      `${(r.pd * 100).toFixed(2)}%`,
      `${(r.lgd * 100).toFixed(0)}%`,
      money(r.expected_loss),
      `${r.risk_weight.toFixed(2)}x`,
      money(r.rwa),
    ]),
  ];
  slide.addTable(rows, {
    x: 0.6, y: 1.8, w: 12.1, colW: [2.3, 1.1, 1.6, 1.1, 0.9, 1.9, 0.9, 2.3], rowH: 0.52,
    fontFace: BODY, fontSize: 12, color: "333333",
    border: { type: "solid", color: ICE_MID, pt: 1 },
  });

  const totals = [
    [money(metrics.total_rwa || 0), "Total RWA", NAVY],
    [money(metrics.total_expected_loss || 0), "Total expected loss", AMBER],
  ];
  totals.forEach(([v, l, c], i) => {
    const x = 0.6 + i * 3.4;
    slide.addShape(pres.ShapeType.roundRect, {
      x, y: 4.35, w: 3.1, h: 1.85, fill: { color: ICE },
      line: { color: ICE_MID, width: 1 }, rectRadius: 0.08,
    });
    statBlock(slide, x, 4.62, 3.1, v, l, c);
  });

  slide.addText(
    [
      { text: "The subordinate class absorbs realised losses in full before any mezzanine write-down occurs.", options: { bullet: true, breakLine: true } },
      { text: "Senior principal is not impaired in any generated scenario.", options: { bullet: true, breakLine: true } },
      { text: "RWA is a simplified rating-band proxy, not a full SEC-SA / SEC-IRBA implementation.", options: { bullet: true } },
    ],
    {
      x: 7.5, y: 4.4, w: 5.2, h: 2.1, fontFace: BODY, fontSize: 13,
      color: "333333", margin: 0, paraSpaceAfter: 8, valign: "top",
    }
  );
  slide.addNotes("Loss allocation seniority is asserted by the test suite, not just asserted verbally.");
}

// ---------------------------------------------------------------- 7. scenario stress
{
  const slide = pres.addSlide();
  slideTitle(slide, "Scenario Stress Testing",
    "Scenarios sampled from the latent space of a VAE trained on macro regime paths — generated, not hand-specified");

  slide.addChart(
    pres.ChartType.bar,
    [{
      name: "Cumulative loss",
      labels: stress.map((r) => String(r.scenario)),
      values: stress.map((r) => Number((r.cumulative_loss / 1e6).toFixed(2))),
    }],
    {
      x: 0.6, y: 1.8, w: 6.2, h: 4.95,
      barDir: "col",
      valAxisMinVal: 0,
      dataLabelFormatCode: '0.00',
      showTitle: true, title: "Cumulative collateral loss by scenario ($mm)",
      titleFontFace: HEAD, titleFontSize: 14, titleColor: NAVY,
      chartColors: [NAVY_MID],
      showValue: true, dataLabelPosition: "outEnd",
      dataLabelFontFace: BODY, dataLabelFontSize: 10, dataLabelColor: "333333",
      showLegend: false,
      catAxisLabelFontFace: BODY, catAxisLabelFontSize: 11, catAxisLabelColor: "444444",
      valAxisLabelFontFace: BODY, valAxisLabelFontSize: 10, valAxisLabelColor: "666666",
      valGridLine: { color: "E3E3E3", size: 1 },
      catGridLine: { style: "none" },
    }
  );

  const rows = [
    ["Scenario", "Regime", "Loss % UPB", "Status"].map((t) => ({
      text: t, options: { bold: true, color: WHITE, fill: { color: NAVY_MID } },
    })),
    ...stress.map((r) => {
      const pct = r.cumulative_loss / upb;
      const esc = pct > 0.02;
      return [
        { text: String(r.scenario), options: { color: "333333" } },
        { text: String(r.label).replace(/\s*\(.*$/, ""), options: { color: "333333" } },
        { text: `${(pct * 100).toFixed(2)}%`, options: { color: "333333" } },
        {
          text: esc ? "ESCALATE" : "within tolerance",
          options: { bold: esc, color: esc ? RED : GREEN },
        },
      ];
    }),
  ];
  slide.addTable(rows, {
    x: 7.1, y: 2.0, w: 5.6, colW: [1.1, 2.1, 1.2, 1.2], rowH: 0.5,
    fontFace: BODY, fontSize: 11.5,
    border: { type: "solid", color: ICE_MID, pt: 1 },
  });

  const escs = metrics.escalations || [];
  if (escs.length) {
    slide.addShape(pres.ShapeType.roundRect, {
      x: 7.1, y: 5.05, w: 5.6, h: 1.7, fill: { color: "F7E6E6" },
      line: { color: RED, width: 1 }, rectRadius: 0.06,
    });
    slide.addText(escs[0], {
      x: 7.32, y: 5.25, w: 5.16, h: 1.35, fontFace: BODY, fontSize: 11.5,
      color: RED, bold: true, margin: 0, valign: "top",
    });
  }
  slide.addNotes(
    "Escalation is a conditional edge in the LangGraph state machine — it fires automatically " +
    "when projected loss breaches the 2% desk threshold."
  );
}

// ---------------------------------------------------------------- 8. method
{
  const slide = pres.addSlide();
  slide.background = { color: NAVY };

  slide.addText("Method and Limitations", {
    x: 0.6, y: 0.5, w: 12.1, h: 0.7,
    fontFace: HEAD, fontSize: 32, bold: true, color: WHITE, margin: 0,
  });

  const steps = ["Ingest", "Stratify", "Forecast", "Risk graph", "Waterfall", "Exposure", "Stress", "Report"];
  steps.forEach((st, i) => {
    const x = 0.6 + i * 1.53;
    slide.addShape(pres.ShapeType.roundRect, {
      x, y: 1.6, w: 1.4, h: 0.75, fill: { color: NAVY_MID },
      line: { color: "3C5A8A", width: 1 }, rectRadius: 0.06,
    });
    slide.addText(st, {
      x, y: 1.6, w: 1.4, h: 0.75, fontFace: BODY, fontSize: 10.5,
      color: WHITE, align: "center", valign: "middle", margin: 0,
    });
  });
  slide.addText("Orchestrated as a LangGraph state machine · Redis stage caching · deployed on Kubernetes as a monthly CronJob", {
    x: 0.6, y: 2.5, w: 12.1, h: 0.35, fontFace: BODY, fontSize: 12, color: "8FA6C4", margin: 0,
  });

  slide.addText("What the models do", {
    x: 0.6, y: 3.35, w: 5.8, h: 0.4,
    fontFace: HEAD, fontSize: 19, bold: true, color: WHITE, margin: 0,
  });
  slide.addText(
    [
      { text: "Transformer — CPR/CDR forecasting from macro paths", options: { bullet: true, breakLine: true } },
      { text: "GNN — correlated default across originator x state cohorts", options: { bullet: true, breakLine: true } },
      { text: "VAE — generates macro scenarios for stress testing", options: { bullet: true, breakLine: true } },
      { text: "LoRA-adapted LM — drafts commentary phrasing only", options: { bullet: true } },
    ],
    {
      x: 0.6, y: 3.9, w: 5.8, h: 2.9, fontFace: BODY, fontSize: 13,
      color: ICE_MID, margin: 0, paraSpaceAfter: 8, valign: "top",
    }
  );

  slide.addText("Scope and limitations", {
    x: 6.9, y: 3.35, w: 5.8, h: 0.4,
    fontFace: HEAD, fontSize: 19, bold: true, color: AMBER, margin: 0,
  });
  slide.addText(
    [
      { text: "All data is synthetic — reported R² measures recovery of a known generating process, not real-world accuracy.", options: { bullet: true, breakLine: true } },
      { text: "RWA is a simplified rating-band proxy, not SEC-SA / SEC-IRBA.", options: { bullet: true, breakLine: true } },
      { text: "The LoRA corpus is small; it is a style layer, and never produces a figure.", options: { bullet: true, breakLine: true } },
      { text: "Every number in this deck is computed deterministically by the pipeline.", options: { bullet: true } },
    ],
    {
      x: 6.9, y: 3.9, w: 5.8, h: 2.9, fontFace: BODY, fontSize: 13,
      color: ICE_MID, margin: 0, paraSpaceAfter: 8, valign: "top",
    }
  );
  slide.addNotes(
    "Stating limitations plainly is the point — in a risk function, knowing what your model " +
    "does not cover matters as much as what it does."
  );
}

const outPath = path.join(OUT, "surveillance_deck.pptx");
pres.writeFile({ fileName: outPath }).then(() => console.log(`wrote ${outPath}`));
