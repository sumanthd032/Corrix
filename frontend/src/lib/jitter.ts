/** Deterministic small per-badge jitter so co-located workers are
 * visually distinct on the heatmap, and stable across re-renders for
 * the same badge ID. Shared between mock data and the live WebSocket
 * stream so worker markers behave identically in both modes. */
export function jitterForBadge(badgeId: string): [number, number] {
  let seed = 0
  for (let i = 0; i < badgeId.length; i++) {
    seed = (seed * 31 + badgeId.charCodeAt(i)) >>> 0
  }
  const a = Math.sin(seed * 12.9898) * 43758.5453
  const b = Math.sin(seed * 78.233) * 12345.6789
  const frac = (n: number) => n - Math.floor(n)
  return [(frac(a) - 0.5) * 20, (frac(b) - 0.5) * 20]
}
