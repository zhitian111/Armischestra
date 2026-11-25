export function inHealthBar(bar, point) {
  return point?.every(
    (n, i) => n >= bar.origin_mm[i] && n <= bar.origin_mm[i] + bar.size_mm[i],
  );
}

export function healthAt(bar, positionOf) {
  return bar.tokens.filter((name) => inHealthBar(bar, positionOf(name))).length;
}

// Dropping the final token or the owner from the cast also removes its empty definition.
export function updateHealthReferences(bars, oldName, newName) {
  return bars.flatMap((bar) => {
    if (!newName && bar.actor === oldName) return [];
    const tokens = bar.tokens.flatMap((t) =>
      t === oldName ? (newName ? [newName] : []) : [t],
    );
    return tokens.length
      ? [{ ...bar, actor: bar.actor === oldName ? newName : bar.actor, tokens }]
      : [];
  });
}

// A tray uses an even square grid. Prefer full 24 mm cards, then fewer rows.
export function layoutTokens(origin, size, count) {
  if (!Number.isInteger(count) || count < 1 || count > 50)
    throw Error("血格数应为 1–50 的整数");
  let best;
  for (let columns = 1; columns <= count; columns++) {
    const rows = Math.ceil(count / columns);
    const pitch = Math.min(size[0] / columns, size[1] / rows);
    const side = Math.min(24, Math.floor(pitch - 2));
    if (
      side >= 16 &&
      (!best || side > best.side || (side === best.side && rows < best.rows))
    )
      best = { columns, rows, side };
  }
  if (!best)
    throw Error(
      "区域放不下这些血块，请扩大宽高或减少格数（每块至少 16 mm，另留 2 mm 间距）。",
    );
  const { columns, rows, side } = best;
  const positions = Array.from({ length: count }, (_, i) =>
    origin.map((v, axis) => {
      const index =
        axis === 0 ? i % columns : rows - 1 - Math.floor(i / columns);
      return Number(
        (
          v +
          ((index + 0.5) * size[axis]) / (axis === 0 ? columns : rows)
        ).toFixed(3),
      );
    }),
  );
  return { side, positions };
}
