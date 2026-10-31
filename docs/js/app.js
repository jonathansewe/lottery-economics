/* Lottery Economics front end. Reads docs/data/*.json (precomputed by
 * `python -m lottery.build`) and renders the landing numbers, the map, the
 * state panels and the EV calculator. Nothing here suggests numbers to play. */
(function () {
  "use strict";
  var ATLAS_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json";
  var D = {};          // loaded JSON
  var byAbbr = {}, byFips = {};

  // ---------- formatting ----------
  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  function money(x, dp) { return "$" + x.toFixed(dp == null ? 2 : dp); }
  function bigMoney(x) {
    if (x >= 1e9) return "$" + (x / 1e9).toFixed(x % 1e9 ? 2 : 0).replace(/\.?0+$/, "") + " billion";
    if (x >= 1e6) return "$" + (x / 1e6).toFixed(x % 1e6 ? 1 : 0).replace(/\.0$/, "") + " million";
    return "$" + Math.round(x).toLocaleString("en-US");
  }
  function oneIn(x) {
    return "1 in " + (x >= 100 ? Math.round(x).toLocaleString("en-US") : x.toFixed(2));
  }
  function pct(x, dp) { return (x * 100).toFixed(dp == null ? 1 : dp) + "%"; }
  function prize(p) { return p === "JACKPOT" ? "Jackpot" : "$" + p.toLocaleString("en-US"); }
  function matchLabel(t, special) {
    if (t.white === 0) return special + " only";
    return t.white + " white" + (t.special ? " + " + special : "");
  }
  var SPECIAL = { powerball: "Powerball", mega_millions: "Mega Ball" };
  var GAME = { powerball: "Powerball", mega_millions: "Mega Millions", ny_numbers: "NY Numbers" };

  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + " " + r.status);
      return r.json();
    });
  }

  // ---------- hero ----------
  function renderHero() {
    var ev = D.ev, h = ev.headline;
    var cards = [
      { g: "powerball", v: h.powerball, sub: "at the " + bigMoney(ev.games.powerball.starting_jackpot) + " starting jackpot, cash option, after taxes" },
      { g: "mega_millions", v: h.mega_millions, sub: "at the " + bigMoney(ev.games.mega_millions.starting_jackpot) + " starting jackpot, cash option, after taxes" },
      { g: "ny_numbers", v: h.ny_numbers, sub: "straight play: fixed $500 prize on a 1-in-1,000 chance, after taxes" }
    ];
    document.getElementById("hero").innerHTML = cards.map(function (c) {
      return '<div class="hero-card"><p class="game">' + GAME[c.g] + '</p>' +
        '<p class="big">' + money(c.v) + ' <small>per $1</small></p>' +
        '<p class="sub">' + esc(c.sub) + '</p></div>';
    }).join("");
    var big = ev.games.powerball.big;
    document.getElementById("hero-note").textContent =
      "Even at a " + bigMoney(big.jackpot) + " Powerball jackpot, $1 is expected to return " + money(big.with_split.total_per_dollar) +
      " once you account for cash value, taxes, and the chance of splitting (assuming " + (big.tickets / 1e6) + " million other tickets). " +
      "Taxes: federal " + pct(ev.tax.federal.rate) + " + NY State " + pct(ev.tax.ny_state.rate, 2) + " + NYC " + pct(ev.tax.nyc.rate, 3) + ".";
  }

  // ---------- map ----------
  function renderMap(us) {
    var el = document.getElementById("map");
    var W = 960, H = 600;
    var states = topojson.feature(us, us.objects.states).features.filter(function (f) { return +f.id <= 56; });
    var proj = d3.geoAlbersUsa().fitSize([W, H], { type: "FeatureCollection", features: states });
    var path = d3.geoPath(proj);
    var svg = d3.select(el).append("svg").attr("viewBox", "0 0 " + W + " " + H).attr("aria-hidden", null);
    var pat = svg.append("defs").append("pattern").attr("id", "hatch").attr("patternUnits", "userSpaceOnUse")
      .attr("width", 8).attr("height", 8).attr("patternTransform", "rotate(45)");
    pat.append("rect").attr("width", 8).attr("height", 8).attr("fill", "var(--surface)");
    pat.append("rect").attr("width", 4).attr("height", 8).attr("fill", "var(--map-none)");
    svg.append("g").selectAll("path").data(states).enter().append("path")
      .attr("d", path)
      .attr("class", function (f) {
        var j = byFips[f.id];
        return "state " + (!j ? "none" : j.deep_dive ? "deep" : j.has_lottery ? "sells" : "none");
      })
      .attr("data-abbr", function (f) { return byFips[f.id] ? byFips[f.id].abbr : ""; })
      .attr("tabindex", 0).attr("role", "button")
      .attr("aria-label", function (f) {
        var j = byFips[f.id];
        if (!j) return f.properties.name;
        return j.name + (j.deep_dive ? ": deep dive" : j.has_lottery ? ": sells " + sellsText(j) : ": no state lottery");
      })
      .on("click", function (e, f) { if (byFips[f.id]) select(byFips[f.id].abbr); })
      .on("keydown", function (e, f) {
        if ((e.key === "Enter" || e.key === " ") && byFips[f.id]) { e.preventDefault(); select(byFips[f.id].abbr); }
      })
      .on("mousemove", function (e, f) {
        var j = byFips[f.id];
        if (j) showStateTip(e, j);
      })
      .on("mouseleave", function () { Charts.hideTip(); });
  }
  function showStateTip(e, j) {
    var t = document.getElementById("tooltip");
    t.innerHTML = "<strong>" + esc(j.name) + "</strong><br>" + (j.deep_dive ? "Deep dive: click to open" : j.has_lottery ? "Sells " + sellsText(j) : "No state lottery");
    t.hidden = false;
    t.style.left = (e.clientX + 14) + "px";
    t.style.top = (e.clientY + 14) + "px";
  }
  function sellsText(j) {
    var g = [];
    if (j.powerball) g.push("Powerball");
    if (j.mega_millions) g.push("Mega Millions");
    return g.join(" and ") || "neither game";
  }
  function renderStateList() {
    var ul = document.getElementById("state-buttons");
    ul.innerHTML = D.states.jurisdictions.slice().sort(function (a, b) { return a.name.localeCompare(b.name); })
      .map(function (j) { return '<li><button type="button" data-open="' + j.abbr + '">' + esc(j.name) + "</button></li>"; }).join("");
  }

  // ---------- panel routing ----------
  function select(abbr) {
    if (location.hash !== "#state=" + abbr) history.replaceState(null, "", "#state=" + abbr);
    openPanel(abbr);
  }
  function openPanel(abbr) {
    var j = byAbbr[abbr];
    if (!j) return;
    d3.selectAll(".map path.state").classed("selected", function () { return this.getAttribute("data-abbr") === abbr; });
    var panel = document.getElementById("panel");
    panel.innerHTML = j.deep_dive ? nyPanel() : statePanel(j);
    panel.querySelector(".close").addEventListener("click", closePanel);
    if (j.deep_dive) initNY(panel);
    panel.focus({ preventScroll: true });
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function closePanel() {
    history.replaceState(null, "", location.pathname);
    d3.selectAll(".map path.state").classed("selected", false);
    document.getElementById("panel").innerHTML =
      '<div class="panel-placeholder muted">Select a state on the map, or <button class="linkish" data-open="NY">open the New York deep dive</button>.</div>';
  }

  function statePanel(j) {
    var link = j.lottery_url
      ? '<a href="' + esc(j.lottery_url) + '" rel="noopener" target="_blank">' + esc(j.lottery_url.replace(/^https?:\/\//, "")) + "</a>" +
        (j.url_verified ? "" : ' <span class="tag" title="This link was not checked when the site was built">link not yet verified</span>')
      : j.has_lottery ? "Official website link not verified yet." : "None: " + esc(j.name) + " has no state lottery.";
    function yn(b) { return b ? "Yes" : "No"; }
    return '<div class="panel"><div class="panel-head"><h2>' + esc(j.name) + '</h2><button class="close" type="button">Close</button></div>' +
      '<div class="facts">' +
      '<div class="fact">Sells Powerball<strong>' + yn(j.powerball) + "</strong></div>" +
      '<div class="fact">Sells Mega Millions<strong>' + yn(j.mega_millions) + "</strong></div>" +
      '<div class="fact">Official lottery website<strong style="font-size:1rem">' + link + "</strong></div></div>" +
      '<p class="notice">Deep dive coming soon. Only New York has historical data and state-specific analysis in this version.</p>' +
      (j.has_lottery ? '<p class="muted">Powerball and Mega Millions use the same numbers and odds everywhere they are sold, so the ' +
        '<button class="linkish" data-open="NY">odds and expected-value math in the New York deep dive</button> apply here too. Only the state and local taxes differ.</p>' : "") +
      "</div>";
  }

  // ---------- NY deep dive ----------
  var TABS = [
    ["games", "Games & odds"], ["ev", "Expected value"], ["freq", "Draw frequencies"],
    ["tests", "Fairness tests"], ["sim", "Hot & cold simulation"]
  ];
  function nyPanel() {
    return '<div class="panel"><div class="panel-head"><div><p class="eyebrow">Deep dive</p><h2>New York</h2></div>' +
      '<button class="close" type="button">Close</button></div>' +
      '<p class="muted">New York sells Powerball, Mega Millions and its own daily Numbers game. The draw history comes from NY Open Data.</p>' +
      '<div class="tabs" role="tablist" aria-label="New York deep dive">' +
      TABS.map(function (t, i) {
        return '<button role="tab" id="tab-' + t[0] + '" aria-controls="tp-' + t[0] + '" aria-selected="' + (i === 0) + '" tabindex="' + (i === 0 ? 0 : -1) + '">' + t[1] + "</button>";
      }).join("") + "</div>" +
      TABS.map(function (t, i) {
        return '<div role="tabpanel" id="tp-' + t[0] + '" aria-labelledby="tab-' + t[0] + '"' + (i ? " hidden" : "") + "></div>";
      }).join("") + "</div>";
  }

  function initNY(panel) {
    var rendered = {};
    var tabs = panel.querySelectorAll('[role="tab"]');
    function show(id) {
      tabs.forEach(function (b) {
        var on = b.id === "tab-" + id;
        b.setAttribute("aria-selected", on);
        b.tabIndex = on ? 0 : -1;
        panel.querySelector("#" + b.getAttribute("aria-controls")).hidden = !on;
      });
      if (!rendered[id]) { RENDER[id](panel.querySelector("#tp-" + id)); rendered[id] = true; }
      else Charts.redrawWithin(panel.querySelector("#tp-" + id));
    }
    tabs.forEach(function (b, i) {
      b.addEventListener("click", function () { show(b.id.slice(4)); });
      b.addEventListener("keydown", function (e) {
        var k = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!k) return;
        var n = tabs[(i + k + tabs.length) % tabs.length];
        n.focus();
        show(n.id.slice(4));
      });
    });
    show("games");
  }

  function noData() {
    return '<div class="notice"><strong>Real draw data has not been loaded into this build.</strong> ' +
      "The charts on this tab come from NY Open Data. Run <code>python -m lottery.build --ingest</code> " +
      "to download the draws and rebuild the site. The <em>Hot &amp; cold simulation</em> tab works without it.</div>";
  }

  var RENDER = {
    games: function (el) {
      var html = "";
      ["powerball", "mega_millions"].forEach(function (g) {
        var G = D.games[g], cur = G.eras.filter(function (e) { return e.era_id === G.current_era; })[0];
        var odds = G.odds[G.current_era];
        html += "<h3>" + GAME[g] + "</h3>" +
          '<div class="facts"><div class="fact">Price per play<strong>' + money(cur.price, 0) + "</strong></div>" +
          '<div class="fact">Draw<strong>' + cur.white_drawn + " of 1–" + cur.white_pool + " + 1 of 1–" + cur.special_pool + "</strong></div>" +
          '<div class="fact">Rules in effect since<strong>' + cur.first_draw + "</strong></div>" +
          '<div class="fact">Any prize<strong>' + oneIn(odds.overall_one_in) + "</strong></div></div>" +
          '<div class="table-scroll"><table><caption>Prize tiers. "Exact" is computed by counting combinations; "Published" is the lottery\'s own figure.</caption>' +
          '<thead><tr><th>Match</th><th class="num">Prize' + (odds.multiplier.length > 1 ? " (base)" : "") + '</th><th class="num">Exact odds</th><th class="num">Published</th></tr></thead><tbody>' +
          odds.tiers.map(function (t) {
            return "<tr><td>" + matchLabel(t, SPECIAL[g]) + '</td><td class="num">' + prize(t.prize) + '</td><td class="num">' +
              oneIn(t.one_in) + '</td><td class="num">' + oneIn(t.official_one_in) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
        if (odds.multiplier.length > 1) {
          html += '<p class="muted">Every $5 Mega Millions play has a built-in multiplier on non-jackpot prizes: ' +
            odds.multiplier.map(function (m) { return m[0] + "× (" + pct(m[1]) + ")"; }).join(", ") +
            ". On average that is ×" + odds.multiplier.reduce(function (s, m) { return s + m[0] * m[1]; }, 0).toFixed(2) + ".</p>";
        }
        html += '<details><summary class="muted">Rule history (eras)</summary><div class="table-scroll"><table><thead><tr><th>Era</th><th>From</th><th>To</th><th class="num">Price</th><th>Verified</th></tr></thead><tbody>' +
          G.eras.map(function (e) {
            return "<tr><td>" + esc(e.label) + "</td><td>" + e.first_draw + "</td><td>" + (e.last_draw || "current") + '</td><td class="num">' +
              money(e.price, 0) + '</td><td style="white-space:normal;min-width:240px" class="fineprint">' + esc(e.verified) + "</td></tr>";
          }).join("") + "</tbody></table></div>" +
          '<p class="fineprint">Sources: ' + cur.sources.map(function (s) { return '<a href="' + esc(s) + '" rel="noopener">' + esc(s.replace(/^https?:\/\//, "").slice(0, 60)) + "</a>"; }).join(" · ") + "</p>" +
          (cur.notes ? '<p class="fineprint">' + esc(cur.notes) + "</p>" : "") + "</details>";
      });
      var N = D.games.ny_numbers;
      html += "<h3>NY Numbers</h3><p class=\"muted\">Three digits, each drawn from 0–9 on its own, so all 1,000 results from 000 to 999 are equally likely. Drawn twice a day.</p>" +
        '<div class="table-scroll"><table><thead><tr><th>Play ($1)</th><th class="num">Prize</th><th class="num">Exact odds</th><th class="num">Published</th></tr></thead><tbody>' +
        N.plays.map(function (p) {
          return "<tr><td>" + esc(p.label) + '</td><td class="num">$' + p.prize + '</td><td class="num">' + oneIn(p.one_in) + '</td><td class="num">1 in ' + p.official_odds + "</td></tr>";
        }).join("") + "</tbody></table></div>" +
        '<p class="fineprint">Source: <a href="' + esc(N.eras[0].sources[0]) + '" rel="noopener">NY Lottery Numbers odds &amp; prizes</a>. ' + esc(N.eras[0].verified) + "</p>";
      el.innerHTML = html;
    },

    ev: function (el) {
      var E = D.ev;
      var html = '<p class="muted">Each bar adds one more piece of reality to the previous one. The vertical line is $1.00, where you would break even on average.</p>';
      var charts = [];
      ["powerball", "mega_millions"].forEach(function (g) {
        var G = E.games[g];
        [["reference", "a quiet draw"], ["big", "a record-style draw"]].forEach(function (sc) {
          var s = G[sc[0]], id = "evc-" + g + "-" + sc[0];
          html += "<h3>" + GAME[g] + ": " + bigMoney(s.jackpot) + " advertised jackpot</h3>" +
            '<p class="fineprint">Scenario: ' + sc[1] + " with " + (s.tickets / 1e6) + " million other tickets (an assumption). Cash value = " +
            pct(s.cash_ratio) + " of the advertised jackpot. Chance someone else also hits: " + pct(s.p_shared) + ".</p>" +
            '<div class="chart" id="' + id + '"></div>';
          charts.push([id, s, g]);
        });
        html += '<p class="muted">Break-even advertised jackpot (no splitting): <strong>' + bigMoney(G.break_even.cash_pre_tax) +
          "</strong> before tax, <strong>" + bigMoney(G.break_even.cash_after_tax) + "</strong> after tax. Bigger jackpots sell more tickets, so splitting pushes the real break-even even higher. It may never be reached.</p>" +
          '<div class="table-scroll"><table><caption>' + GAME[g] + ": chance of sharing the jackpot (Poisson model)</caption><thead><tr><th>Other tickets sold</th><th class=\"num\">P(someone else also wins)</th><th class=\"num\">Expected share you keep</th></tr></thead><tbody>" +
          G.split_grid.map(function (r) {
            return "<tr><td>" + (r.tickets / 1e6) + ' million</td><td class="num">' + pct(r.p_shared) + '</td><td class="num">' + pct(r.expected_share) + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      });
      html += "<h3>NY Numbers</h3><p class=\"muted\">Prizes are fixed, so the return never changes: </p><ul class=\"plain\">" +
        E.numbers.map(function (n) { return "<li>" + esc(n.label) + ": <strong>" + money(n.ev_per_dollar) + "</strong> back per $1 before tax, " + money(n.after_tax_per_dollar) + " after tax owed</li>"; }).join("") + "</ul>" +
        "<h3>Tax assumptions</h3><div class=\"table-scroll\"><table><thead><tr><th>Tax</th><th class=\"num\">Rate</th><th>How it was checked</th></tr></thead><tbody>" +
        [["Federal (top bracket)", "federal", 1], ["New York State (top bracket)", "ny_state", 2], ["New York City (top bracket)", "nyc", 3]].map(function (t) {
          return "<tr><td>" + t[0] + '</td><td class="num">' + pct(E.tax[t[1]].rate, t[2]) + '</td><td class="fineprint" style="white-space:normal">' + esc(E.tax[t[1]].verified) + "</td></tr>";
        }).join("") + "</tbody></table></div>" +
        '<p class="fineprint">All gambling winnings are taxable income, so every prize, even $4, is taxed here at the top marginal rates. That overstates tax for most people on small prizes. The calculator also has a <em>withholding only</em> view: ' +
        pct(E.withholding.federal.rate, 0) + " federal + NYS + NYC withheld on prizes over $" + E.withholding_threshold.toLocaleString("en-US") +
        ". That is what is taken when you claim, not what you finally owe.</p>";
      el.innerHTML = html;
      charts.forEach(function (c) {
        var s = c[1];
        Charts.hbar(document.getElementById(c[0]), [
          { label: "Advertised", value: s.advertised.total_per_dollar, note: "annuity jackpot, no tax, no sharing" },
          { label: "Cash value", value: s.cash.total_per_dollar, note: "lump sum instead of 30-year annuity" },
          { label: "After tax", value: s.after_tax.total_per_dollar, note: "federal + NY State + NYC" },
          { label: "With splitting", value: s.with_split.total_per_dollar, note: "expected share of a shared jackpot" }
        ], { ref: 1, refLabel: "$1 break-even", ariaLabel: GAME[c[2]] + " expected return per dollar, step by step" });
      });
    },

    freq: function (el) {
      if (!D.stats.data_available) { el.innerHTML = noData(); return; }
      var F = D.stats.frequencies;
      var games = [];
      F.forEach(function (f) { if (games.indexOf(f.game) < 0) games.push(f.game); });
      el.innerHTML = '<p class="muted">How often each ball came up, counted separately for each rule era. The shaded band is where a single ball\'s count lands 95% of the time if the draws are fair, so about 5% of the bars should stick out by chance alone. The line is the expected count.</p>' +
        '<div class="chart-controls"><label>Game<select id="fq-game">' + games.map(function (g) { return '<option value="' + g + '">' + GAME[g] + "</option>"; }).join("") + "</select></label>" +
        '<label>Era<select id="fq-era"></select></label><label>Balls<select id="fq-set"></select></label></div>' +
        '<p class="fineprint" id="fq-note"></p><div class="chart" id="fq-chart"></div>' +
        '<details class="as-table"><summary>Show as table</summary><div class="table-scroll" id="fq-table"></div></details>';
      var gS = el.querySelector("#fq-game"), eS = el.querySelector("#fq-era"), sS = el.querySelector("#fq-set");
      function opts(sel, items) { sel.innerHTML = items.map(function (i) { return '<option value="' + i[0] + '">' + esc(i[1]) + "</option>"; }).join(""); }
      var SETNAME = { white: "White balls", special: "Powerball / Mega Ball", digit_1: "1st digit", digit_2: "2nd digit", digit_3: "3rd digit", number: "Whole number (000–999)" };
      function refreshEras() {
        var seen = {}, items = [];
        F.filter(function (f) { return f.game === gS.value; }).forEach(function (f) {
          if (!seen[f.era_id]) { seen[f.era_id] = 1; items.push([f.era_id, f.era_label + " (" + f.n_draws + " draws)"]); }
        });
        opts(eS, items.reverse());
        refreshSets();
      }
      function refreshSets() {
        opts(sS, F.filter(function (f) { return f.era_id === eS.value; }).map(function (f) {
          return [f.ball_set, f.ball_set === "special" ? SPECIAL[f.game] : SETNAME[f.ball_set]];
        }));
        draw();
      }
      function draw() {
        var f = F.filter(function (x) { return x.era_id === eS.value && x.ball_set === sS.value; })[0];
        if (!f) return;
        el.querySelector("#fq-note").textContent = f.first_draw + " to " + f.last_draw + ": " + f.n_draws + " draws. " +
          f.outside_band + " of " + f.counts.length + " outside the fair 95% band (expect about " + f.expected_outside + " by chance).";
        Charts.columns(el.querySelector("#fq-chart"), {
          labels: f.labels, counts: f.counts, expected: f.expected, band: f.band95,
          unit: f.game === "ny_numbers" ? (f.ball_set === "number" ? "Number" : "Digit") : "Ball"
        }, { ariaLabel: "Frequency of each " + (f.game === "ny_numbers" ? "digit or number" : "ball") + ", " + f.era_label });
        el.querySelector("#fq-table").innerHTML = "<table><thead><tr><th>Value</th><th class=\"num\">Times drawn</th><th class=\"num\">Expected</th></tr></thead><tbody>" +
          f.labels.map(function (l, i) { return "<tr><td>" + l + '</td><td class="num">' + f.counts[i] + '</td><td class="num">' + f.expected.toFixed(1) + "</td></tr>"; }).join("") + "</tbody></table>";
      }
      gS.addEventListener("change", refreshEras);
      eS.addEventListener("change", refreshSets);
      sS.addEventListener("change", draw);
      refreshEras();
    },

    tests: function (el) {
      if (!D.stats.data_available) { el.innerHTML = noData(); return; }
      var T = D.stats.tests, n = T.length, a = D.stats.alpha;
      var flagged = T.filter(function (t) { return t.significant; }).length;
      el.innerHTML = '<p class="muted">A chi-square goodness-of-fit test asks: if every ball were equally likely, how surprising would counts this uneven be? ' +
        "The p-value is that probability. We ran " + n + " tests (one per game, era and set of balls), so we use a Bonferroni correction: a result only counts as evidence of bias if p &lt; " +
        a + " ÷ " + n + " = " + (a / n).toPrecision(2) + ". Without that, roughly 1 in 20 fair tests would look 'significant' by luck alone.</p>" +
        '<p><strong>' + (flagged === 0 ? "No test shows evidence of non-random draws." : flagged + " of " + n + " tests fall below the corrected threshold. See the notes below.") + "</strong></p>" +
        '<div class="table-scroll"><table><thead><tr><th>Game</th><th>Era</th><th>Balls</th><th class="num">Draws</th><th class="num">χ²</th><th class="num">df</th><th class="num">p-value</th><th class="num">Bonferroni p</th><th>Result</th></tr></thead><tbody>' +
        T.map(function (t) {
          return "<tr><td>" + GAME[t.game] + "</td><td>" + esc(t.era_label) + "</td><td>" + esc(t.ball_set.replace("_", " ")) + '</td><td class="num">' + t.n_draws +
            '</td><td class="num">' + t.statistic.toFixed(1) + '</td><td class="num">' + t.df + '</td><td class="num">' + t.p_value.toPrecision(3) +
            '</td><td class="num">' + t.p_bonferroni.toPrecision(3) + '</td><td><span class="verdict' + (t.significant ? " flag" : "") + '">' +
            (t.significant ? "Uneven beyond chance" : "Consistent with fair") + (t.min_expected_ok ? "" : " (small sample)") + "</span></td></tr>";
        }).join("") + "</tbody></table></div>" +
        '<p class="fineprint">White balls are drawn 5 at a time without replacement, so the usual statistic is multiplied by (m−1)/(m−k), for example 68/64 for Powerball. Without this correction the test is too lenient. "Small sample" means fewer than 5 expected draws per ball, where the chi-square approximation is unreliable. Even a flagged result says nothing about which numbers will come up next.</p>';
    },

    sim: function (el) {
      var S = D.sim.simulations;
      // with real data, compare against fair histories of the same length
      function ens(s) { return s.real_ensemble || s; }
      var html = '<p class="muted">These draws are generated by a perfectly fair random number generator, so by construction no number is "due" or "hot". The charts still show hot and cold numbers anyway.</p>';
      S.forEach(function (s, i) {
        var ex = s.example;
        html += "<h3>" + esc(s.era_label) + ": " + s.n_draws.toLocaleString("en-US") + " fair simulated draws</h3>" +
          '<div class="chart" id="sim-ex-' + i + '"></div>' +
          '<p class="muted">In this fake data the "hottest" balls were ' + ex.hot.join(", ") + ' and the "coldest" were ' + ex.cold.join(", ") +
          ". The gap between the most and least drawn ball is " + ex.spread + " draws, which is pure luck. Re-run the simulation with another seed and an entirely different set comes out on top.</p>" +
          '<div class="chart" id="sim-spread-' + i + '"></div>' +
          '<p class="fineprint">' + (s.real ? "Compared against " + s.histories.toLocaleString("en-US") + " fair histories of the same length as the real data (" + s.real.n_draws.toLocaleString("en-US") + " draws)" : "Across " + s.histories.toLocaleString("en-US") + " fair histories") +
          ", the hot-to-cold gap ranged from " + Math.round(ens(s).spread.p05) + " to " + Math.round(ens(s).spread.p95) + " (5th–95th percentile). " +
          (s.real ? "The real draws (black line) sit at the " + Math.round(s.real.spread_percentile) + "th percentile." : "Real data will be marked here once it is ingested.") + "</p>" +
          '<div class="chart" id="sim-persist-' + i + '"></div>' +
          '<p class="fineprint">Do hot numbers stay hot? Each fair history is split in half, and the rank correlation between first-half and second-half counts is measured. Fair data centres on 0 (mean ' +
          ens(s).persistence.mean.toFixed(3) + "), meaning past frequency says nothing about the future. " +
          (s.real ? "Real draws: " + s.real.persistence.toFixed(3) + ". The 10 most-drawn balls in the first half averaged " + s.real.first_half_hot_second_half_avg.toFixed(1) +
            " draws in the second half, against " + s.real.second_half_expected.toFixed(1) + " expected for any ball." : "") + "</p>";
      });
      el.innerHTML = html;
      S.forEach(function (s, i) {
        Charts.columns(el.querySelector("#sim-ex-" + i), { labels: s.example.labels, counts: s.example.counts, expected: s.expected, band: s.band95, sim: true },
          { ariaLabel: "Counts per ball in one fair simulated history" });
        var real = s.real, E = ens(s);
        // spread histogram: values_hist is indexed by spread value
        var sh = E.spread.values_hist, first = sh.findIndex(function (c) { return c > 0; });
        Charts.histogram(el.querySelector("#sim-spread-" + i), {
          counts: sh.slice(first), x0: first, binWidth: 1,
          marker: real ? real.spread : null,
          xLabel: "hot-to-cold gap (draws)"
        }, { ariaLabel: "Distribution of hot-to-cold gap in fair data" });
        Charts.histogram(el.querySelector("#sim-persist-" + i), {
          counts: E.persistence.hist, x0: -1, binWidth: 0.1, xmin: -1, xmax: 1, fmt: d3.format(".1f"),
          marker: real ? real.persistence : null, markerLabel: "real draws",
          xLabel: "first-half vs second-half correlation"
        }, { ariaLabel: "Distribution of half-to-half correlation in fair data" });
      });
    }
  };

  // ---------- calculator ----------
  function initCalc() {
    var E = D.ev;
    var q = function (id) { return document.getElementById(id); };
    function mode() { return document.querySelector('input[name="tax-mode"]:checked').value; }
    function rates() { return mode() === "withholding" ? E.withholding : E.tax; }
    function showRates() {
      var R = rates();
      q("rate-federal").textContent = "(" + pct(R.federal.rate) + ")";
      q("rate-state").textContent = "(" + pct(R.ny_state.rate, 2) + ")";
      q("rate-city").textContent = "(" + pct(R.nyc.rate, 3) + ")";
    }
    showRates();
    document.querySelectorAll('input[name="tax-mode"]').forEach(function (r) {
      r.addEventListener("change", function () { showRates(); run(); });
    });
    function setCash() { q("calc-cash").value = E.games[q("calc-game").value].cash_ratio; }
    setCash();
    q("calc-game").addEventListener("change", function () { setCash(); run(); });
    ["calc-jackpot", "calc-cash", "calc-tickets", "tax-federal", "tax-state", "tax-city"].forEach(function (id) {
      q(id).addEventListener("input", run);
    });
    function num(id, lo, hi) {
      var v = parseFloat(q(id).value);
      if (!isFinite(v)) return null;
      return Math.min(hi, Math.max(lo, v));
    }
    function run() {
      var gk = q("calc-game").value, G = E.games[gk];
      var jackpot = num("calc-jackpot", 0, 1e11), cash = num("calc-cash", 0.01, 1), tickets = num("calc-tickets", 0, 5e9);
      var out = q("calc-out");
      if (jackpot == null || cash == null || tickets == null) { out.innerHTML = '<p class="muted">Enter a number in each box.</p>'; return; }
      var R = rates(), threshold = E.tax_modes[mode()].threshold;
      var rate = (q("tax-federal").checked ? R.federal.rate : 0) + (q("tax-state").checked ? R.ny_state.rate : 0) + (q("tax-city").checked ? R.nyc.rate : 0);
      var r = LotteryEV.evBreakdown(G, { jackpot: jackpot, cashRatio: cash, tickets: tickets, taxRate: rate, threshold: threshold });
      var be = LotteryEV.breakEvenJackpot(G, cash, rate, threshold);
      var v = r.with_split.total_per_dollar;
      out.innerHTML = '<p class="calc-big">' + money(v) + ' <small class="muted" style="font-size:1rem;font-weight:500">expected back per $1</small></p>' +
        '<p class="muted">You lose ' + money(1 - v) + " per dollar on average" + (v >= 1 ? " (this scenario is above break-even, which in practice almost never holds once ticket sales are realistic)" : "") +
        ". The chance another ticket also hits the jackpot is " + pct(r.p_shared) + ", so on average you'd keep " + pct(r.expected_share) +
        " of it. Break-even jackpot with these settings, ignoring splitting: " + bigMoney(be) + ".</p>" +
        '<div class="chart" id="calc-chart"></div>';
      Charts.hbar(q("calc-chart"), [
        { label: "Advertised", value: r.advertised.total_per_dollar },
        { label: "Cash value", value: r.cash.total_per_dollar },
        { label: "After tax", value: r.after_tax.total_per_dollar },
        { label: "With splitting", value: r.with_split.total_per_dollar }
      ], { ref: 1, refLabel: "$1", ariaLabel: "Expected return per dollar for the calculator's inputs" });
    }
    run();
  }

  // ---------- boot ----------
  function boot() {
    document.addEventListener("click", function (e) {
      var b = e.target.closest("[data-open]");
      if (b) { e.preventDefault(); select(b.getAttribute("data-open")); }
    });
    Promise.all(["games", "ev", "stats", "simulation", "states"].map(function (n) { return getJSON("data/" + n + ".json"); }))
      .then(function (r) {
        D = { games: r[0], ev: r[1], stats: r[2], sim: r[3], states: r[4] };
        D.states.jurisdictions.forEach(function (j) { byAbbr[j.abbr] = j; byFips[j.fips] = j; });
        renderHero();
        renderStateList();
        initCalc();
        document.getElementById("generated").textContent = "Built " + D.ev.generated_at.slice(0, 10) +
          (D.stats.data_available ? "" : ". Draw data not yet ingested.");
        document.getElementById("sources").innerHTML = 'Sources: rules and prizes from <a href="https://www.powerball.com/powerball-prize-chart">powerball.com</a>, ' +
          '<a href="https://www.megamillions.com/how-to-play.aspx">megamillions.com</a> and <a href="https://nylottery.ny.gov">nylottery.ny.gov</a>; draws from ' +
          '<a href="https://data.ny.gov">NY Open Data</a>. Every figure lists how it was checked in the Games &amp; odds tab.';
        var m = /state=([A-Z]{2})/.exec(location.hash);
        if (m) openPanel(m[1]);
        return getJSON(ATLAS_URL).then(renderMap);
      })
      .catch(function (err) {
        console.error(err);
        var msg = '<p class="notice">Some data could not load (' + esc(err.message) + "). If you opened this file directly, serve the folder instead: <code>python -m http.server -d docs</code>.</p>";
        if (!D.ev) document.getElementById("hero").innerHTML = msg;
        else document.getElementById("map").innerHTML = msg;
      });
  }
  boot();
})();
