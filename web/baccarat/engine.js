(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.BaccaratEngine = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';
  function normalizeHands(hands) {
    return (Array.isArray(hands) ? hands : []).filter(h => h && typeof h === 'object' && ['P', 'B', 'T'].includes(h.outcome)).map((h, i) => ({id: h.id || i + 1,outcome: h.outcome,playerPair: !!h.playerPair,bankerPair: !!h.bankerPair,ts: h.ts || null,special:h.special || null}));
  }
  function logicalColumns(hands) {
    const cols = [];
    for (const h of normalizeHands(hands)) {
      if (h.outcome === 'T') continue;
      const last = cols[cols.length - 1];
      if (!last || last.outcome !== h.outcome) cols.push({ outcome: h.outcome, hands: [h] });
      else last.hands.push(h);
    }
    return cols;
  }
  function placeRoadMarks(marks, rows = 6) {
    const grid = new Map(), cells = []; let lastMark = null, streakStartCol = 0, lastCell = null;
    const occupied = (c, r) => grid.has(`${c},${r}`);
    for (let i = 0; i < marks.length; i++) {
      const mark = marks[i]; let col, row;
      if (!lastCell) { col = 0; row = 0; streakStartCol = 0; }
      else if (mark === lastMark) {
        const down = lastCell.row + 1;
        if (down < rows && !occupied(lastCell.col, down)) { col = lastCell.col; row = down; }
        else { col = lastCell.col + 1; row = lastCell.row; while (occupied(col, row)) col++; }
      } else { col = streakStartCol + 1; row = 0; while (occupied(col, row)) col++; streakStartCol = col; }
      const cell = { index: i, mark, col, row }; cells.push(cell); grid.set(`${col},${row}`, cell); lastCell = cell; lastMark = mark;
    }
    return { cells, maxCol: cells.reduce((m, c) => Math.max(m, c.col), 0), grid };
  }
  function buildBigRoad(hands) {
    const hs = normalizeHands(hands), decisive = []; let pendingTies = 0, pendingTiePairs = { playerPair:false, bankerPair:false };
    for (const h of hs) {
      if (h.outcome === 'T') {
        if (decisive.length) {
          const prev = decisive[decisive.length - 1];
          prev.tieCount = (prev.tieCount || 0) + 1;
          prev.tiePlayerPair = prev.tiePlayerPair || h.playerPair;
          prev.tieBankerPair = prev.tieBankerPair || h.bankerPair;
        } else {
          pendingTies++; pendingTiePairs.playerPair ||= h.playerPair; pendingTiePairs.bankerPair ||= h.bankerPair;
        }
        continue;
      }
      const item = { outcome:h.outcome, playerPair:h.playerPair, bankerPair:h.bankerPair, tieCount:pendingTies, tiePlayerPair:pendingTiePairs.playerPair, tieBankerPair:pendingTiePairs.bankerPair };
      pendingTies = 0; pendingTiePairs = { playerPair:false, bankerPair:false }; decisive.push(item);
    }
    const placement = placeRoadMarks(decisive.map(x => x.outcome));
    return { cells: placement.cells.map((c, i) => ({ ...c, ...decisive[i] })), maxCol: placement.maxCol, initialTieCount: decisive.length ? 0 : pendingTies };
  }
  function derivedMarks(hands, offset) {
    const cols = logicalColumns(hands), marks = [];
    for (let c = 0; c < cols.length; c++) {
      const currentLen = cols[c].hands.length;
      for (let r = 1; r <= currentLen; r++) {
        if (r === 1) {
          if (c < offset + 1) continue;
          // On a new streak compare the preceding streak with the one k columns before it.
          // Use logical (unlimited-height) columns, never the wrapped screen coordinates.
          const a = cols[c - 1].hands.length, b = cols[c - offset - 1].hands.length;
          marks.push(a === b ? 'R' : 'U');
        } else {
          if (c < offset) continue;
          const refLen = cols[c - offset].hands.length, sameRowExists = refLen >= r, aboveExists = refLen >= (r - 1);
          marks.push(sameRowExists === aboveExists ? 'R' : 'U');
        }
      }
    }
    return marks;
  }
  function buildDerivedRoad(hands, offset) {
    const marks = derivedMarks(hands, offset), placement = placeRoadMarks(marks);
    return { marks, cells: placement.cells, maxCol: placement.maxCol };
  }
  function beadCells(hands) { return normalizeHands(hands).map((h, i) => ({ ...h, row: i % 6, col: Math.floor(i / 6) })); }
  function stats(hands) {
    const hs = normalizeHands(hands), total = hs.length, banker = hs.filter(h => h.outcome === 'B').length, player = hs.filter(h => h.outcome === 'P').length, tie = hs.filter(h => h.outcome === 'T').length, bankerPair = hs.filter(h => h.bankerPair).length, playerPair = hs.filter(h => h.playerPair).length;
    const decisive = hs.filter(h => h.outcome !== 'T'); let currentStreak = { outcome:null, count:0 }, maxStreak = { outcome:null, count:0 };
    for (const h of decisive) { if (h.outcome === currentStreak.outcome) currentStreak.count++; else currentStreak = { outcome:h.outcome, count:1 }; if (currentStreak.count > maxStreak.count) maxStreak = { ...currentStreak }; }
    return { total, banker, player, tie, bankerPair, playerPair, currentStreak, maxStreak };
  }
  return { normalizeHands, logicalColumns, placeRoadMarks, buildBigRoad, buildDerivedRoad, beadCells, stats };
});
