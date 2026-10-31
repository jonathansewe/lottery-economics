/* Small D3 chart helpers. Every chart measures its container, so text stays
 * readable on phones (no viewBox scaling), and re-renders on resize. */
(function (root) {
  "use strict";
  var tip = function () { return document.getElementById("tooltip"); };

  function showTip(evt, html) {
    var t = tip();
    t.innerHTML = html;
    t.hidden = false;
    var x = evt.clientX + 14, y = evt.clientY + 14;
    var r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - 14;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - 14;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  function hideTip() { tip().hidden = true; }

  var registry = [];
  var resizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      registry = registry.filter(function (r) { return document.body.contains(r.el); });
      registry.forEach(function (r) { if (visible(r.el) && r.el.clientWidth !== r.width) r.draw(); });
    }, 150);
  });
  // A chart inside a hidden tab measures 0 wide, so it is skipped here and
  // drawn by redrawWithin() when its tab is shown.
  function visible(el) { return el.offsetParent !== null && el.clientWidth > 0; }
  function responsive(el, draw) {
    var entry = { el: el, width: null };
    entry.draw = function () { entry.width = el.clientWidth; draw(); };
    registry = registry.filter(function (r) { return r.el !== el; });
    registry.push(entry);
    if (visible(el)) entry.draw();
  }
  function redrawWithin(container) {
    registry.forEach(function (r) {
      if (container.contains(r.el) && visible(r.el) && r.el.clientWidth !== r.width) r.draw();
    });
  }

  function frame(el, height, margin) {
    el.innerHTML = "";
    var w = Math.max(280, el.clientWidth || 600);
    var svg = d3.select(el).append("svg").attr("width", w).attr("height", height);
    return { svg: svg, w: w, h: height, iw: w - margin.left - margin.right, ih: height - margin.top - margin.bottom,
             g: svg.append("g").attr("transform", "translate(" + margin.left + "," + margin.top + ")") };
  }

  /* Horizontal bars: rows [{label, value, note}], refLine at x = opts.ref */
  function hbar(el, rows, opts) {
    opts = opts || {};
    responsive(el, function () {
      var narrow = (el.clientWidth || 600) < 480;
      var m = { top: 8, right: 56, bottom: 28, left: narrow ? 104 : 150 };
      var f = frame(el, m.top + m.bottom + rows.length * 38, m);
      f.svg.attr("role", "img").attr("aria-label", opts.ariaLabel || "");
      var max = Math.max(opts.ref || 0, d3.max(rows, function (r) { return r.value; })) * 1.05;
      var x = d3.scaleLinear().domain([0, max]).range([0, f.iw]);
      var y = d3.scaleBand().domain(rows.map(function (r) { return r.label; })).range([0, f.ih]).padding(0.32);
      f.g.append("g").attr("class", "axis").attr("transform", "translate(0," + f.ih + ")")
        .call(d3.axisBottom(x).ticks(narrow ? 3 : 5).tickFormat(opts.format || d3.format("$.2f")));
      f.g.selectAll(".ylab").data(rows).enter().append("text").attr("class", "label")
        .attr("x", -8).attr("y", function (r) { return y(r.label) + y.bandwidth() / 2; })
        .attr("dy", "0.35em").attr("text-anchor", "end").text(function (r) { return r.label; });
      f.g.selectAll(".bar").data(rows).enter().append("rect").attr("class", "bar")
        .attr("x", 0).attr("y", function (r) { return y(r.label); })
        .attr("width", function (r) { return Math.max(1, x(r.value)); }).attr("height", y.bandwidth()).attr("rx", 3)
        .on("mousemove", function (e, r) { showTip(e, "<strong>" + r.label + "</strong><br>" + (opts.format || d3.format("$.3f"))(r.value) + (r.note ? "<br>" + r.note : "")); })
        .on("mouseleave", hideTip);
      f.g.selectAll(".val").data(rows).enter().append("text").attr("class", "label")
        .attr("x", function (r) { return x(r.value) + 6; }).attr("y", function (r) { return y(r.label) + y.bandwidth() / 2; })
        .attr("dy", "0.35em").text(function (r) { return (opts.format || d3.format("$.2f"))(r.value); });
      if (opts.ref) {
        f.g.append("line").attr("class", "ref").attr("x1", x(opts.ref)).attr("x2", x(opts.ref)).attr("y1", -4).attr("y2", f.ih);
        f.g.append("text").attr("class", "label muted").attr("x", x(opts.ref) + 4).attr("y", f.ih - 4)
          .attr("font-size", 11).text(opts.refLabel || "");
      }
    });
  }

  /* Count per ball with expected line and 95% fair band.
   * d: {labels, counts, expected, band:[lo,hi], sim:bool, unit} */
  function columns(el, d, opts) {
    opts = opts || {};
    responsive(el, function () {
      var m = { top: 12, right: 8, bottom: 30, left: 40 };
      var f = frame(el, opts.height || 220, m);
      f.svg.attr("role", "img").attr("aria-label", opts.ariaLabel || "");
      var many = d.labels.length > 120;
      var x = d3.scaleBand().domain(d.labels.map(String)).range([0, f.iw]).padding(many ? 0 : 0.18);
      var y = d3.scaleLinear().domain([0, Math.max(d3.max(d.counts), d.band[1]) * 1.08]).nice().range([f.ih, 0]);
      f.g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(4).tickSize(-f.iw).tickFormat(""))
        .call(function (g) { g.select(".domain").remove(); });
      f.g.append("rect").attr("class", "band").attr("x", 0).attr("width", f.iw)
        .attr("y", y(d.band[1])).attr("height", Math.max(0, y(d.band[0]) - y(d.band[1])));
      var step = Math.ceil(d.labels.length / Math.max(4, Math.floor(f.iw / 34)));
      f.g.append("g").attr("class", "axis").attr("transform", "translate(0," + f.ih + ")")
        .call(d3.axisBottom(x).tickValues(d.labels.map(String).filter(function (_, i) { return i % step === 0; })).tickSizeOuter(0));
      f.g.append("g").attr("class", "axis").call(d3.axisLeft(y).ticks(4));
      var data = d.labels.map(function (l, i) { return { label: String(l), count: d.counts[i] }; });
      f.g.selectAll(".bar").data(data).enter().append("rect")
        .attr("class", "bar" + (d.sim ? " sim" : ""))
        .attr("x", function (r) { return x(r.label); }).attr("width", Math.max(0.5, x.bandwidth()))
        .attr("y", function (r) { return y(r.count); }).attr("height", function (r) { return f.ih - y(r.count); })
        .attr("rx", many ? 0 : Math.min(3, x.bandwidth() / 3))
        .on("mousemove", function (e, r) {
          showTip(e, "<strong>" + (d.unit || "Ball") + " " + r.label + "</strong><br>drawn " + r.count +
            " times<br>expected " + d.expected.toFixed(1) + " (fair 95% range " + d.band[0] + "–" + d.band[1] + ")");
        })
        .on("mouseleave", hideTip);
      // invisible wider hit targets for thin bars
      if (x.bandwidth() < 6) {
        f.g.selectAll(".hit").data(data).enter().append("rect").attr("fill", "transparent")
          .attr("x", function (r) { return x(r.label) - 2; }).attr("width", x.bandwidth() + 4)
          .attr("y", 0).attr("height", f.ih)
          .on("mousemove", function (e, r) {
            showTip(e, "<strong>" + (d.unit || "Ball") + " " + r.label + "</strong><br>drawn " + r.count + " times<br>expected " + d.expected.toFixed(1));
          })
          .on("mouseleave", hideTip);
      }
      f.g.append("line").attr("class", "ref").attr("x1", 0).attr("x2", f.iw).attr("y1", y(d.expected)).attr("y2", y(d.expected));
    });
  }

  /* Histogram of a simulated distribution with an optional marker for the real value.
   * d: {counts (per bin), x0, binWidth, marker, markerLabel, xLabel, fmt} */
  function histogram(el, d, opts) {
    opts = opts || {};
    responsive(el, function () {
      var m = { top: 22, right: 12, bottom: 40, left: 40 };
      var f = frame(el, 200, m);
      f.svg.attr("role", "img").attr("aria-label", opts.ariaLabel || "");
      var bins = d.counts.map(function (c, i) { return { x0: d.x0 + i * d.binWidth, x1: d.x0 + (i + 1) * d.binWidth, c: c }; });
      var lo = d.xmin != null ? d.xmin : bins[0].x0, hi = d.xmax != null ? d.xmax : bins[bins.length - 1].x1;
      if (d.marker != null) { lo = Math.min(lo, d.marker); hi = Math.max(hi, d.marker + d.binWidth); }
      var x = d3.scaleLinear().domain([lo, hi]).range([0, f.iw]);
      var y = d3.scaleLinear().domain([0, d3.max(bins, function (b) { return b.c; }) * 1.1]).nice().range([f.ih, 0]);
      f.g.append("g").attr("class", "axis").attr("transform", "translate(0," + f.ih + ")").call(d3.axisBottom(x).ticks(6).tickFormat(d.fmt || null));
      f.g.append("g").attr("class", "axis").call(d3.axisLeft(y).ticks(3));
      f.g.append("text").attr("class", "label muted").attr("x", f.iw / 2).attr("y", f.ih + 34).attr("text-anchor", "middle").attr("font-size", 11).text(d.xLabel || "");
      f.g.selectAll(".bar").data(bins).enter().append("rect").attr("class", "bar sim")
        .attr("x", function (b) { return x(b.x0) + 1; }).attr("width", function (b) { return Math.max(0.5, x(b.x1) - x(b.x0) - 2); })
        .attr("y", function (b) { return y(b.c); }).attr("height", function (b) { return f.ih - y(b.c); }).attr("rx", 2)
        .on("mousemove", function (e, b) {
          var f2 = d.fmt || d3.format(".0f");
          showTip(e, f2(b.x0) + (d.binWidth > 1 || d.fmt ? "–" + f2(b.x1) : "") + ": " + b.c + " fair histories");
        })
        .on("mouseleave", hideTip);
      if (d.marker != null) {
        var mx = x(d.marker);
        f.g.append("line").attr("class", "marker").attr("x1", mx).attr("x2", mx).attr("y1", -6).attr("y2", f.ih);
        f.g.append("text").attr("class", "label").attr("x", mx).attr("y", -10)
          .attr("text-anchor", mx > f.iw * 0.7 ? "end" : "start").text(d.markerLabel || "real data");
      }
    });
  }

  /* Lines over time: series [{name, points:[{x: Date, y}]}], at most 3 (fixed colour order). */
  function lines(el, series, opts) {
    opts = opts || {};
    var colors = ["var(--accent)", "var(--series-2)", "var(--series-3)"];
    responsive(el, function () {
      var m = { top: 12, right: 12, bottom: 30, left: 52 };
      el.innerHTML = "";
      var legend = d3.select(el).append("div").attr("class", "legend");
      series.forEach(function (s, i) {
        legend.append("span").html('<i class="swatch" style="background:' + colors[i] + '"></i>' + s.name.replace(/</g, "&lt;"));
      });
      var w = Math.max(280, el.clientWidth || 600);
      var svg = d3.select(el).append("svg").attr("width", w).attr("height", 240).attr("role", "img").attr("aria-label", opts.ariaLabel || "");
      var iw = w - m.left - m.right, ih = 240 - m.top - m.bottom;
      var g = svg.append("g").attr("transform", "translate(" + m.left + "," + m.top + ")");
      var all = [].concat.apply([], series.map(function (s) { return s.points; }));
      var x = d3.scaleTime().domain(d3.extent(all, function (p) { return p.x; })).range([0, iw]);
      var y = d3.scaleLinear().domain([0, d3.max(all, function (p) { return p.y; }) * 1.1]).nice().range([ih, 0]);
      g.append("g").attr("class", "grid").call(d3.axisLeft(y).ticks(4).tickSize(-iw).tickFormat("")).call(function (a) { a.select(".domain").remove(); });
      g.append("g").attr("class", "axis").attr("transform", "translate(0," + ih + ")").call(d3.axisBottom(x).ticks(Math.max(2, Math.floor(iw / 90))));
      g.append("g").attr("class", "axis").call(d3.axisLeft(y).ticks(4).tickFormat(opts.yFormat || null));
      series.forEach(function (s, i) {
        var pts = s.points.slice().sort(function (a, b) { return a.x - b.x; });
        g.append("path").datum(pts).attr("fill", "none").attr("stroke", colors[i]).attr("stroke-width", 2)
          .attr("d", d3.line().x(function (p) { return x(p.x); }).y(function (p) { return y(p.y); }));
        g.selectAll(".pt" + i).data(pts).enter().append("circle").attr("r", 4).attr("fill", colors[i])
          .attr("stroke", "var(--surface)").attr("stroke-width", 2)
          .attr("cx", function (p) { return x(p.x); }).attr("cy", function (p) { return y(p.y); })
          .on("mousemove", function (e, p) { showTip(e, "<strong>" + s.name.replace(/</g, "&lt;") + "</strong><br>" + p.x.toISOString().slice(0, 10) + ": " + Math.round(p.y).toLocaleString("en-US") + " tickets"); })
          .on("mouseleave", hideTip);
      });
    });
  }

  root.Charts = { hbar: hbar, columns: columns, histogram: histogram, lines: lines, hideTip: hideTip, redrawWithin: redrawWithin };
})(this);
