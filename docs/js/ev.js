/* Expected-value math for the in-browser calculator.
 * A line-for-line port of lottery/math.py (ev_breakdown, expected_share,
 * fixed_prize_ev, break_even_jackpot). tests/test_js_parity.py runs this file
 * under Node and checks it against the Python results.
 * Inputs come from docs/data/ev.json (tiers with exact probabilities). */
(function (root) {
  "use strict";

  // E[1/(K+1)] for K ~ Poisson(lam): (1 - e^-lam) / lam
  function expectedShare(pJackpot, otherTickets) {
    var lam = pJackpot * otherTickets;
    if (lam === 0) return 1;
    return -Math.expm1(-lam) / lam;
  }

  function pShared(pJackpot, otherTickets) {
    return -Math.expm1(-pJackpot * otherTickets);
  }

  // threshold 0 = tax owed on every prize; 5000 = the "withholding only" view
  function taxed(amount, rate, threshold) {
    return amount <= threshold ? amount : amount * (1 - rate);
  }

  function fixedPrizeEV(game, taxRate, threshold) {
    var total = 0;
    game.tiers.forEach(function (t) {
      if (t.prize === "JACKPOT") return;
      var sum = 0;
      game.multiplier.forEach(function (fq) {
        sum += fq[1] * taxed(t.prize * fq[0], taxRate, threshold);
      });
      total += t.probability * sum;
    });
    return total;
  }

  function jackpotProbability(game) {
    return game.tiers.filter(function (t) { return t.prize === "JACKPOT"; })[0].probability;
  }

  /* opts: {jackpot, cashRatio, tickets, taxRate, threshold} -> per-$1 steps */
  function evBreakdown(game, opts) {
    var pj = jackpotProbability(game);
    var share = expectedShare(pj, opts.tickets);
    var fixedPre = fixedPrizeEV(game, 0, 0);
    var fixedPost = fixedPrizeEV(game, opts.taxRate, opts.threshold);
    var cash = opts.jackpot * opts.cashRatio;
    var steps = {
      advertised: [fixedPre, pj * opts.jackpot],
      cash: [fixedPre, pj * cash],
      after_tax: [fixedPost, pj * cash * (1 - opts.taxRate)],
      with_split: [fixedPost, pj * cash * (1 - opts.taxRate) * share]
    };
    var out = { p_jackpot: pj, p_shared: pShared(pj, opts.tickets), expected_share: share };
    Object.keys(steps).forEach(function (k) {
      out[k] = {
        fixed_per_dollar: steps[k][0] / game.price,
        jackpot_per_dollar: steps[k][1] / game.price,
        total_per_dollar: (steps[k][0] + steps[k][1]) / game.price
      };
    });
    return out;
  }

  function breakEvenJackpot(game, cashRatio, taxRate, threshold) {
    var pj = jackpotProbability(game);
    var fixed = fixedPrizeEV(game, taxRate, threshold);
    return (game.price - fixed) / (pj * cashRatio * (1 - taxRate));
  }

  var api = {
    expectedShare: expectedShare, pShared: pShared, fixedPrizeEV: fixedPrizeEV,
    evBreakdown: evBreakdown, breakEvenJackpot: breakEvenJackpot
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.LotteryEV = api;
})(this);
