/* NY deep-dive tabs added in v2: odds for every game, EV table for every game,
 * draw history, number checker and ticket-sales chart. Called from app.js with the
 * loaded data D. Nothing here suggests numbers; the checker only describes a pick. */
(function (root) {
  "use strict";

  var GAME_ORDER = ["powerball", "mega_millions", "ny_lotto", "take5", "ny_numbers", "win4",
                    "pick10", "quick_draw", "millionaire_for_life", "cash4life"];
  var SPECIAL_NAME = { powerball: "Powerball", mega_millions: "Mega Ball", ny_lotto: "Bonus",
                       cash4life: "Cash Ball", millionaire_for_life: "Millionaire Ball" };
  var PAGE = 25;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; });
  }
  function money(x, dp) { return "$" + Number(x).toFixed(dp == null ? 2 : dp); }
  function dollars(x) { return "$" + Math.round(x).toLocaleString("en-US"); }
  function oneIn(x) { return x == null ? "—" : "1 in " + (x >= 100 ? Math.round(x).toLocaleString("en-US") : x.toFixed(2)); }
  function pct(x, dp) { return (x * 100).toFixed(dp == null ? 1 : dp) + "%"; }
  var UNV = ' <span class="unv" title="Not confirmed from an official page">unverified</span>';
  function unv(flag) { return flag === false ? UNV : ""; }
  function games(D) { return GAME_ORDER.filter(function (g) { return D.games[g]; }); }
  function era(D, g) { var G = D.games[g]; return G.eras.filter(function (e) { return e.era_id === G.current_era; })[0]; }
  function comb(n, k) { var c = 1; for (var i = 0; i < k; i++) c = c * (n - i) / (i + 1); return Math.round(c); }

  function prizeText(r) {
    if (r.prize === "PARIMUTUEL") return esc(r.label || "Pari-mutuel") + (r.typical_prize ? " · typically " + dollars(r.typical_prize) : "");
    if (r.prize === "FREE_PLAY") return esc(r.label || "Free play");
    if (r.prize === "JACKPOT") return "Jackpot";
    return (r.label ? esc(r.label) : dollars(r.prize));
  }
  function matchText(g, r, e) {
    if (e.kind === "keno") return r.white + " of your numbers";
    var s = r.white + (e.white_drawn > 1 ? " numbers" : "");
    if (r.special === 1) return s + " + " + (SPECIAL_NAME[g] || "special");
    if (r.special === 0 && e.special_pool && !e.bonus) return r.white === 0 ? "none" : s + " (no " + (SPECIAL_NAME[g] || "special") + ")";
    if (r.special === 0 && e.bonus) return s + " (no bonus)";
    return s;
  }

  // ---------------------------------------------------------------- odds, all games
  function oddsTable(D, g) {
    var G = D.games[g], e = era(D, g), O = G.odds[G.current_era];
    var head = "<h3>" + esc(G.label) + "</h3>" +
      '<div class="facts"><div class="fact">Price<strong>' + money(e.price) + (e.plays_per_dollar > 1 ? " per play ($1 buys " + e.plays_per_dollar + ")" : "") + "</strong></div>" +
      '<div class="fact">Draw<strong>' + esc(e.matrix) + "</strong></div>" +
      '<div class="fact">Rules since<strong>' + e.first_draw + (e.unverified.indexOf("first_draw") >= 0 ? UNV : "") + "</strong></div>" +
      (e.last_draw ? '<div class="fact">Last draw<strong>' + e.last_draw + " (retired)</strong></div>" : "") +
      (e.prize_pool_fraction ? '<div class="fact">Paid out as prizes<strong>' + pct(e.prize_pool_fraction, 0) + " of sales</strong></div>" : "") + "</div>";
    var cov = D.draws && D.draws.games[g] ? '<p class="fineprint">Data coverage: ' + esc(D.draws.games[g].coverage) + "</p>" : "";
    var body;
    if (O.tiers) {
      body = tbl(["Match", "Prize", "Exact odds", "Published"], O.tiers.map(function (r) {
        return [matchText(g, r, e), prizeText(r) + unv(r.verified), oneIn(r.one_in), oneIn(r.official_one_in)];
      }), [false, false, true, true]);
    } else if (O.plays) {
      body = tbl(["Play ($1)", "Prize", "Exact odds", "Published"], O.plays.map(function (r) {
        return [esc(r.label), dollars(r.prize) + unv(r.verified), oneIn(r.one_in), r.official_odds ? "1 in " + r.official_odds : "—"];
      }), [false, true, true, true]);
    } else {
      var keys = Object.keys(O).filter(function (k) { return /-spot$/.test(k); });
      body = keys.map(function (k) {
        return "<h4>" + k + ' <span class="fineprint">any prize ' + oneIn(O.overall[k]) + " (published " + oneIn(O.official_overall[k]) + ")</span></h4>" +
          tbl(["Match", "Prize", "Exact odds", "Published"], O[k].map(function (r) {
            return [matchText(g, r, e), dollars(r.prize) + unv(r.verified), oneIn(r.one_in), oneIn(r.official_one_in)];
          }), [false, true, true, true]);
      }).join("");
    }
    var meta = '<details><summary class="muted">Sources and verification</summary><p class="fineprint">' + esc(e.verified) + "</p>" +
      (e.unverified.length ? '<p class="fineprint">Unverified: ' + e.unverified.map(esc).join("; ") + "</p>" : "") +
      (e.notes ? '<p class="fineprint">' + esc(e.notes) + "</p>" : "") +
      '<p class="fineprint">' + e.sources.map(function (s) { return '<a href="' + esc(s) + '" rel="noopener">' + esc(s.replace(/^https?:\/\//, "").slice(0, 70)) + "</a>"; }).join("<br>") + "</p></details>";
    return head + cov + body + meta;
  }

  function tbl(headers, rows, num) {
    return '<div class="table-scroll"><table><thead><tr>' + headers.map(function (h, i) {
      return '<th' + (num && num[i] ? ' class="num"' : "") + ">" + h + "</th>";
    }).join("") + "</tr></thead><tbody>" + rows.map(function (r) {
      return "<tr>" + r.map(function (c, i) { return "<td" + (num && num[i] ? ' class="num"' : "") + ">" + c + "</td>"; }).join("") + "</tr>";
    }).join("") + "</tbody></table></div>";
  }

  function gamesTab(el, D) {
    var gs = games(D);
    el.innerHTML = '<p class="muted">Every major game the New York Lottery sells or recently sold. "Exact odds" come from counting combinations. ' +
      '"Published" is the lottery\'s own figure. Values we could not confirm from an official page are marked' + UNV + ".</p>" +
      '<div class="chart-controls"><label>Game<select id="go-game">' + gs.map(function (g) {
        return '<option value="' + g + '">' + esc(D.games[g].label) + "</option>";
      }).join("") + '</select></label></div><div id="go-body"></div>';
    var sel = el.querySelector("#go-game");
    function draw() { el.querySelector("#go-body").innerHTML = oddsTable(D, sel.value); }
    sel.addEventListener("change", draw);
    draw();
  }

  // ---------------------------------------------------------------- EV, all games
  function evTable(D) {
    var rows = [];
    ["powerball", "mega_millions"].forEach(function (g) {
      var R = D.ev.games[g].reference;
      rows.push([esc(D.games[g].label), "at the " + dollars(R.jackpot) + " starting jackpot", money(R.cash.total_per_dollar),
                 money(R.with_split.total_per_dollar), money(D.ev.games[g].reference_withholding.with_split.total_per_dollar)]);
    });
    games(D).forEach(function (g) {
      var G = D.games[g];
      if (!G.ev) return;
      G.ev.owed.forEach(function (r, i) {
        var w = G.ev.withholding[i];
        rows.push([esc(G.label) + (G.retired ? " (retired)" : ""), esc(r.label || r.play) + unv(r.verified),
                   money(r.pre_tax), money(r.after_tax), money(w.after_tax)]);
      });
    });
    return "<h3>Every NY game, per $1</h3>" +
      tbl(["Game", "Play", "Before tax", "After tax owed", "After withholding only"], rows, [false, false, true, true, true]) +
      '<p class="fineprint">Pari-mutuel games (NY Lotto, Take 5) return their prize-pool share of sales on average, because rollovers only move money between draws. ' +
      "\"For life\" prizes are valued at the lump-sum cash option. Prizes marked" + UNV + " use amounts we could not confirm.</p>";
  }

  // ---------------------------------------------------------------- draw history
  var cache = {};
  function loadFile(f) {
    if (!cache[f]) cache[f] = fetch("data/draws/" + f).then(function (r) { if (!r.ok) throw new Error(f); return r.json(); });
    return cache[f];
  }

  function historyTab(el, D) {
    var gs = games(D);
    el.innerHTML = '<div class="subtabs" role="tablist" aria-label="Game">' + gs.map(function (g, i) {
      return '<button role="tab" data-g="' + g + '" aria-selected="' + (i === 0) + '">' + esc(D.games[g].label) + "</button>";
    }).join("") + '</div><div id="hist-body"></div>';
    var buttons = el.querySelectorAll(".subtabs button");
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        buttons.forEach(function (x) { x.setAttribute("aria-selected", x === b); });
        historyGame(el.querySelector("#hist-body"), D, b.getAttribute("data-g"));
      });
    });
    historyGame(el.querySelector("#hist-body"), D, gs[0]);
  }

  function historyGame(el, D, g) {
    var idx = D.draws && D.draws.games[g];
    var G = D.games[g];
    if (!idx || !idx.available) {
      el.innerHTML = '<div class="notice"><strong>' + esc(G.label) + ": data not ingested yet.</strong> " + esc(idx ? idx.coverage : "") +
        (idx && idx.dataset_id ? " Source: NY Open Data <code>" + esc(idx.dataset_id) + "</code>. Run <code>python -m lottery.build --ingest</code>." :
          " No NY Open Data dataset has been identified for this game yet.") + "</div>";
      return;
    }
    var periods = idx.files.map(function (f) { return f.period; }).reverse();
    el.innerHTML = '<p class="fineprint">' + esc(idx.coverage) + (idx.largest_gap_days > 7 ? " Longest gap between draws: " + idx.largest_gap_days + " days (shown as-is, never filled in)." : "") + "</p>" +
      '<div class="chart-controls"><label>Period<select class="h-period"><option value="__all">All' + (idx.recent_only ? " recent" : "") + " (" + idx.files.length + " files)</option>" +
      periods.map(function (p, i) { return '<option value="' + p + '"' + (i === 0 ? " selected" : "") + ">" + p + "</option>"; }).join("") + "</select></label>" +
      '<label>Date starts with<input class="h-date" placeholder="2024-05" size="10"></label>' +
      '<label>Contains number<input class="h-num" inputmode="numeric" size="6"></label>' +
      '<button type="button" class="close h-csv">Download CSV</button></div><div class="h-table" aria-live="polite"></div>';
    var st = { rows: [], sortDir: -1, page: 0 };
    var q = function (c) { return el.querySelector(c); };
    function load() {
      var p = q(".h-period").value;
      var files = idx.files.filter(function (f) { return p === "__all" || f.period === p; });
      q(".h-table").innerHTML = '<p class="muted">Loading…</p>';
      Promise.all(files.map(function (f) { return loadFile(f.file); })).then(function (parts) {
        st.rows = [].concat.apply([], parts.map(function (x) { return x.rows; }));
        st.page = 0;
        render();
      }).catch(function (e) { q(".h-table").innerHTML = '<p class="notice">Could not load ' + esc(e.message) + "</p>"; });
    }
    function filtered() {
      var d = q(".h-date").value.trim(), n = q(".h-num").value.trim();
      return st.rows.filter(function (r) {
        if (d && r[0].indexOf(d) !== 0) return false;
        if (!n) return true;
        if (typeof r[2] === "string") return r[2].indexOf(n) >= 0;
        var v = +n;
        return r[2].indexOf(v) >= 0 || r[3] === v;
      }).sort(function (a, b) {
        var c = a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : (a[5] || 0) - (b[5] || 0) || String(a[1]).localeCompare(String(b[1]));
        return c * st.sortDir;
      });
    }
    var hasTime = function () { return st.rows.some(function (r) { return r[1]; }); };
    var hasNo = function () { return st.rows.some(function (r) { return r[5] != null; }); };
    var hasSpecial = function () { return st.rows.some(function (r) { return r[3] != null; }); };
    var hasMult = function () { return st.rows.some(function (r) { return r[4] != null; }); };
    function render() {
      var rows = filtered(), pages = Math.max(1, Math.ceil(rows.length / PAGE));
      st.page = Math.min(st.page, pages - 1);
      var slice = rows.slice(st.page * PAGE, st.page * PAGE + PAGE);
      var heads = ['<button type="button" class="sort" aria-label="Sort by date">Date ' + (st.sortDir < 0 ? "▼" : "▲") + "</button>"];
      if (hasTime()) heads.push("Draw");
      if (hasNo()) heads.push("Draw #");
      heads.push("Numbers");
      if (hasSpecial()) heads.push(SPECIAL_NAME[g] || "Special");
      if (hasMult()) heads.push("Multiplier");
      q(".h-table").innerHTML = '<p class="fineprint">' + rows.length.toLocaleString("en-US") + " draws match.</p>" +
        tbl(heads, slice.map(function (r) {
          var c = [r[0]];
          if (hasTime()) c.push(esc(r[1] || ""));
          if (hasNo()) c.push(r[5] == null ? "" : r[5]);
          c.push(typeof r[2] === "string" ? r[2] : r[2].join(" "));
          if (hasSpecial()) c.push(r[3] == null ? "" : r[3]);
          if (hasMult()) c.push(r[4] == null ? "" : r[4] + "×");
          return c;
        })) +
        '<div class="pager"><button type="button" class="close h-prev"' + (st.page === 0 ? " disabled" : "") + '>Previous</button> <span>Page ' + (st.page + 1) + " of " + pages +
        '</span> <button type="button" class="close h-next"' + (st.page >= pages - 1 ? " disabled" : "") + ">Next</button></div>";
      q(".sort").addEventListener("click", function () { st.sortDir *= -1; render(); });
      q(".h-prev").addEventListener("click", function () { st.page--; render(); });
      q(".h-next").addEventListener("click", function () { st.page++; render(); });
    }
    q(".h-period").addEventListener("change", load);
    q(".h-date").addEventListener("input", function () { st.page = 0; render(); });
    q(".h-num").addEventListener("input", function () { st.page = 0; render(); });
    q(".h-csv").addEventListener("click", function () {
      var rows = filtered();
      var lines = [["date", "draw_time", "numbers", "special", "multiplier", "draw_number"].join(",")].concat(rows.map(function (r) {
        return [r[0], r[1] || "", typeof r[2] === "string" ? r[2] : r[2].join(" "), r[3] == null ? "" : r[3], r[4] == null ? "" : r[4], r[5] == null ? "" : r[5]].join(",");
      }));
      var a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
      a.download = g + "-" + q(".h-period").value.replace("__all", "all") + ".csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
    load();
  }

  // ---------------------------------------------------------------- number checker
  function parseNums(s) { return (s.match(/\d+/g) || []).map(Number); }

  function patternWarnings(nums, e) {
    var w = [], s = nums.slice().sort(function (a, b) { return a - b; });
    if (e.white_pool > 31 && s.length >= 3 && s[s.length - 1] <= 31) w.push("All your numbers are 31 or under. Many people play birthdays and anniversaries, so these combinations are over-played.");
    var run = 1, best = 1;
    for (var i = 1; i < s.length; i++) { run = s[i] === s[i - 1] + 1 ? run + 1 : 1; best = Math.max(best, run); }
    if (best >= 3) w.push("Contains a run of " + best + " consecutive numbers. Sequences are a popular pattern.");
    if (s.length >= 4) {
      var d = s[1] - s[0], ap = d > 1 && s.every(function (x, j) { return j === 0 || x - s[j - 1] === d; });
      if (ap) w.push("Your numbers are evenly spaced (every " + d + "). Patterns like this are popular.");
    }
    if (s.length >= 3 && s.every(function (x) { return x % 10 === s[0] % 10; })) w.push("All your numbers end in the same digit, another common pattern.");
    if (s.length >= 3 && s.every(function (x) { return x % 5 === 0; })) w.push("All multiples of 5, a common pattern.");
    return w;
  }
  function digitWarnings(str) {
    var w = [];
    if (/^(\d)\1+$/.test(str)) w.push("All digits are the same (" + str + "). Repeated digits are among the most-played numbers.");
    var up = str.split("").every(function (c, i, a) { return i === 0 || +c === +a[i - 1] + 1; });
    var down = str.split("").every(function (c, i, a) { return i === 0 || +c === +a[i - 1] - 1; });
    if (up || down) w.push("A straight sequence (" + str + "). Sequences are heavily played.");
    if (str.length === 4 && str.slice(0, 2) === str.slice(2)) w.push("A repeated pair pattern (" + str + "), also popular.");
    return w;
  }

  function checkerTab(el, D) {
    var gs = games(D);
    el.innerHTML = '<p class="muted">Enter a pick for any game. The checker validates it against the game\'s rules, gives its exact odds, and counts how often it came up in past draws. ' +
      "It also flags patterns many other people play. It does <strong>not</strong> rate picks as better or worse: every valid combination has exactly the same odds.</p>" +
      '<form class="calc" id="ck-form" onsubmit="return false"><label>Game<select id="ck-game">' + gs.map(function (g) {
        return '<option value="' + g + '">' + esc(D.games[g].label) + "</option>";
      }).join("") + '</select></label><label id="ck-main-l">Your numbers<input id="ck-main" autocomplete="off"></label>' +
      '<label id="ck-sp-l">Special ball<input id="ck-sp" inputmode="numeric" autocomplete="off"></label>' +
      '<label id="ck-play-l">Play type<select id="ck-play"><option value="straight">Straight (exact order)</option><option value="box">Box (any order)</option></select></label>' +
      '<div><button type="submit" class="close" id="ck-go">Check</button></div></form><div id="ck-out" aria-live="polite"></div>';
    var q = function (c) { return el.querySelector(c); };
    function setup() {
      var g = q("#ck-game").value, e = era(D, g);
      q("#ck-sp-l").hidden = !(e.kind === "lotto" && e.special_pool && !e.bonus);
      q("#ck-play-l").hidden = e.kind !== "digits";
      var hint = e.kind === "digits" ? e.white_drawn + " digits, e.g. " + "0123456789".slice(0, e.white_drawn)
        : e.kind === "keno" ? (g === "pick10" ? "exactly 10" : "1 to 10") + " numbers from 1–" + e.white_pool
        : e.white_drawn + " numbers from 1–" + e.white_pool;
      q("#ck-main").placeholder = hint;
      q("#ck-main-l").firstChild.textContent = "Your numbers (" + hint + ")";
      q("#ck-sp").placeholder = e.special_pool ? "1–" + e.special_pool : "";
      q("#ck-out").innerHTML = "";
    }
    q("#ck-game").addEventListener("change", setup);
    q("#ck-go").addEventListener("click", function () { check(q("#ck-out"), D, q("#ck-game").value, q("#ck-main").value, q("#ck-sp").value, q("#ck-play").value); });
    setup();
  }

  function check(out, D, g, mainStr, spStr, play) {
    var e = era(D, g), G = D.games[g], errs = [], warn = [], html = "";
    var noSplit = "This game pays fixed prizes, so a popular pick wins exactly the same amount as any other.";
    var split = "Popular picks don't lose more often, because every combination is equally likely. But when they win, they split shared prizes more often, so on average they pay less.";
    if (e.kind === "digits") {
      var str = mainStr.replace(/\s+/g, "");
      if (!new RegExp("^\\d{" + e.white_drawn + "}$").test(str)) errs.push("Enter exactly " + e.white_drawn + " digits (0–9).");
      else {
        var counts = {}; str.split("").forEach(function (c) { counts[c] = (counts[c] || 0) + 1; });
        var ways = 1, f = 1; for (var i = 2; i <= str.length; i++) f *= i;
        Object.keys(counts).forEach(function (k) { var c = 1; for (var j = 2; j <= counts[k]; j++) c *= j; f /= c; });
        ways = play === "box" ? f : 1;
        if (play === "box" && f === 1) errs.push("A box play needs at least two different digits; " + str + " can only be played straight.");
        else {
          var total = Math.pow(10, e.white_drawn);
          html += "<h3>Odds</h3><p><strong>1 in " + (total / ways).toLocaleString("en-US", { maximumFractionDigits: 2 }) + "</strong> for a " + play + " play" +
            (play === "box" ? " (" + ways + "-way: covers " + ways + " of the " + total.toLocaleString("en-US") + " results)" : "") +
            ". Every " + e.white_drawn + "-digit result is equally likely, so 0000 is as likely as 4831.</p>";
          warn = digitWarnings(str);
          html += historyDigits(D, g, str, play);
        }
      }
    } else {
      var nums = parseNums(mainStr), k = e.kind === "keno" ? nums.length : e.white_drawn;
      var uniq = nums.filter(function (x, i) { return nums.indexOf(x) === i; });
      if (e.kind === "keno" && (nums.length < 1 || nums.length > 10)) errs.push("Pick between 1 and 10 numbers.");
      if (g === "pick10" && nums.length !== 10) errs.push("Pick 10 needs exactly 10 numbers.");
      if (e.kind === "lotto" && nums.length !== k) errs.push("Enter exactly " + k + " numbers.");
      if (uniq.length !== nums.length) errs.push("Each number can be used only once.");
      if (nums.some(function (x) { return x < 1 || x > e.white_pool; })) errs.push("Numbers must be between 1 and " + e.white_pool + ".");
      var sp = null;
      if (e.kind === "lotto" && e.special_pool && !e.bonus) {
        sp = parseInt(spStr, 10);
        if (!(sp >= 1 && sp <= e.special_pool)) errs.push((SPECIAL_NAME[g] || "Special ball") + " must be between 1 and " + e.special_pool + ".");
      }
      if (!errs.length) {
        var O = G.odds[G.current_era];
        if (e.kind === "keno") {
          var rows = O[nums.length + "-spot"];
          html += "<h3>Odds for a " + nums.length + "-spot play</h3>" + tbl(["Match", "Prize", "Exact odds"], rows.map(function (r) {
            return [r.white + " of " + nums.length, dollars(r.prize) + unv(r.verified), oneIn(r.one_in)];
          }), [false, true, true]) + "<p>Any " + nums.length + " numbers have exactly these odds. Which numbers you choose makes no difference.</p>";
        } else {
          var combos = comb(e.white_pool, e.white_drawn) * (e.special_pool && !e.bonus ? e.special_pool : 1);
          html += "<h3>Odds</h3><p>Top prize: <strong>1 in " + combos.toLocaleString("en-US") + "</strong>. That's the number of possible tickets, and yours is exactly one of them, like every other. " +
            "Any prize: " + oneIn(O.overall_one_in) + ".</p>";
        }
        warn = patternWarnings(nums, e);
        html += historyLotto(D, g, nums, sp, e);
      }
    }
    if (errs.length) { out.innerHTML = '<div class="notice"><strong>Not a valid ' + esc(G.label) + " pick:</strong><ul>" + errs.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul></div>"; return; }
    var pari = ["powerball", "mega_millions", "ny_lotto", "take5"].indexOf(g) >= 0;
    html += "<h3>Popular patterns</h3>" + (warn.length ? "<ul class=\"plain\">" + warn.map(function (x) { return "<li>" + x + "</li>"; }).join("") + "</ul>" : "<p>No common pattern detected.</p>") +
      "<p class=\"muted\">" + (pari ? split : noSplit + (g === "pick10" ? " (Exception: Pick 10's top prize is capped at $5 million in total, so it is shared if more than 10 tickets win it.)" : "")) + "</p>";
    out.innerHTML = html;
  }

  function freqFor(D, g, set) {
    return (D.stats.frequencies || []).filter(function (f) { return f.game === g && f.era_id === D.games[g].current_era && f.ball_set === set; })[0];
  }

  function historyLotto(D, g, nums, sp, e) {
    var idx = D.draws && D.draws.games[g];
    if (!idx || !idx.available) return '<h3>History</h3><p class="notice">Draw data not ingested yet, so there is nothing to count. The odds above don\'t depend on history anyway.</p>';
    var F = freqFor(D, g, "white");
    var per = F ? "<p>Times each of your numbers was drawn in the current rules era (" + F.n_draws.toLocaleString("en-US") + " draws, expected " + F.expected.toFixed(1) + " each): " +
      nums.map(function (n) { return n + ": " + F.counts[n - 1]; }).join(", ") + ". These counts say nothing about the next draw.</p>" : "";
    var id = "ck-hist-" + Date.now();
    Promise.all(idx.files.map(function (f) { return loadFile(f.file); })).then(function (parts) {
      var hits = 0, total = 0, last = null, set = {};
      nums.forEach(function (n) { set[n] = 1; });
      parts.forEach(function (p) {
        p.rows.forEach(function (r) {
          total++;
          var all = nums.every(function (n) { return r[2].indexOf(n) >= 0; });
          var exact = e.kind === "keno" ? all : all && r[2].length === nums.length && (sp == null || r[3] === sp);
          if (exact) { hits++; if (!last || r[0] > last) last = r[0]; }
        });
      });
      var el = document.getElementById(id);
      if (el) el.innerHTML = (e.kind === "keno" ? "All your numbers were among the 20 drawn in " : "This exact combination was drawn in ") +
        "<strong>" + hits + "</strong> of " + total.toLocaleString("en-US") + " draws on file" + (last ? " (most recently " + last + ")" : "") + "." +
        (idx.recent_only ? " Quick Draw: recent years only." : "");
    });
    return "<h3>History</h3>" + per + '<p id="' + id + '">Searching past draws…</p>';
  }

  function historyDigits(D, g, str, play) {
    var idx = D.draws && D.draws.games[g];
    if (!idx || !idx.available) return '<h3>History</h3><p class="notice">Draw data not ingested yet, so there is nothing to count.</p>';
    var id = "ck-hist-" + Date.now(), key = str.split("").sort().join("");
    Promise.all(idx.files.map(function (f) { return loadFile(f.file); })).then(function (parts) {
      var straight = 0, box = 0, total = 0;
      parts.forEach(function (p) { p.rows.forEach(function (r) { total++; if (r[2] === str) straight++; if (r[2].split("").sort().join("") === key) box++; }); });
      var el = document.getElementById(id);
      if (el) el.innerHTML = str + " came up exactly <strong>" + straight + "</strong> times, and in any order <strong>" + box + "</strong> times, in " + total.toLocaleString("en-US") + " draws.";
    });
    return "<h3>History</h3><p id=\"" + id + "\">Searching past draws…</p>";
  }

  // ---------------------------------------------------------------- ticket sales
  function salesTab(el, D) {
    var S = D.sales;
    var shares = tbl(["Game", "Share of sales funding the jackpot", "Scope"], Object.keys(S.shares).map(function (g) {
      var s = S.shares[g];
      return [esc(D.games[g].label), s.share == null ? "not found: method (a) off" : pct(s.share, 0) + (s.verified ? "" : UNV), S.scope[g] === "national" ? "national (all states)" : "New York only"];
    }));
    var intro = '<p class="muted">Two independent estimates of tickets sold per draw: <strong>(a)</strong> how much the cash jackpot grew, divided by the share of sales that funds it; ' +
      "<strong>(b)</strong> how many people won each prize tier, divided by that tier's odds. " +
      "<strong>Powerball and Mega Millions estimates are national</strong> (all participating states), not New York's sales.</p>";
    if (!S.available) {
      el.innerHTML = intro + '<div class="notice"><strong>No sales inputs yet.</strong> The estimator needs jackpot amounts and winner counts per draw from the official sites, ' +
        "which were unreachable when this was built. The input files are <code>data/sales/*.csv</code>; see <code>data/sales/README.md</code>.</div>" + shares;
      return;
    }
    var series = {};
    S.estimates.forEach(function (r) {
      var key = D.games[r.game].label + " · " + (r.method === "winner_counts" ? "winners" : "jackpot growth") + " · " + r.scope;
      (series[key] = series[key] || []).push({ x: new Date(r.draw_date), y: r.tickets });
    });
    el.innerHTML = intro + '<div class="chart" id="sales-chart"></div>' +
      (S.comparisons.length ? "<h3>Against official sales</h3>" + tbl(["Game", "Method", "Period", "Official tickets", "Estimated", "Error"], S.comparisons.map(function (c) {
        return [esc(D.games[c.game].label), esc(c.method), c.period_start + " – " + c.period_end, Math.round(c.official_tickets).toLocaleString("en-US"),
                Math.round(c.estimated_tickets).toLocaleString("en-US"), (c.error_pct >= 0 ? "+" : "") + c.error_pct.toFixed(1) + "%"];
      }), [false, false, false, true, true, true]) : '<p class="fineprint">No official sales figures loaded, so the error can\'t be reported yet.</p>') + shares;
    Charts.lines(el.querySelector("#sales-chart"), Object.keys(series).slice(0, 3).map(function (k) { return { name: k, points: series[k] }; }),
      { ariaLabel: "Estimated tickets sold per draw", yFormat: d3.format(".2s") });
  }

  root.NYGames = { gamesTab: gamesTab, evTable: evTable, historyTab: historyTab, checkerTab: checkerTab, salesTab: salesTab };
})(this);
