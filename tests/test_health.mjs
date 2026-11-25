import assert from "node:assert/strict";
import { test } from "node:test";
import {
  healthAt,
  layoutTokens,
  updateHealthReferences,
} from "../editor/health.js";
const bar = {
  name: "黑龙血条",
  actor: "黑龙",
  origin_mm: [10, 20],
  size_mm: [30, 20],
  tokens: ["甲", "乙"],
};

test("replay counts owned pieces by pickup point, including edges", () => {
  const frame = { 甲: [10, 20], 乙: [40, 40], 丙: [22, 31] };
  assert.equal(
    healthAt(bar, (n) => frame[n]),
    2,
  );
  frame.乙 = [40.01, 40];
  assert.equal(
    healthAt(bar, (n) => frame[n]),
    1,
  );
  frame.甲 = [9, 20];
  assert.equal(
    healthAt(bar, (n) => frame[n]),
    0,
  );
});

test("auto-placement wraps rows, preserves printable size and allows each token room", () => {
  const { positions, side } = layoutTokens([10, 10], [56, 55], 4);
  assert.equal(side, 24);
  assert.equal(positions.length, 4);
  for (const [i, a] of positions.entries()) {
    assert.ok(a[0] - side / 2 >= 10 && a[1] + side / 2 <= 65);
    for (const b of positions.slice(0, i))
      assert.ok(a.some((n, k) => Math.abs(n - b[k]) >= side + 2));
  }
  assert.throws(() => layoutTokens([0, 0], [20, 20], 2), /放不下/);
});

test("renaming and deleting pieces leave no orphan owners or blood tokens", () => {
  let bars = updateHealthReferences([bar], "黑龙", "龙");
  bars = updateHealthReferences(bars, "甲", "壹");
  assert.equal(bars[0].actor, "龙");
  assert.deepEqual(bars[0].tokens, ["壹", "乙"]);
  assert.deepEqual(updateHealthReferences(bars, "龙", null), []);
  bars = updateHealthReferences(bars, "乙", null);
  assert.deepEqual(bars[0].tokens, ["壹"]);
  assert.deepEqual(updateHealthReferences(bars, "壹", null), []);
});
