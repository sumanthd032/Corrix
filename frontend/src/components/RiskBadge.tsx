import { AlertTriangle, CircleCheck, OctagonAlert, Square } from 'lucide-react'
import type { RiskLevel } from '../types'

/**
 * Every risk-state indicator in the app must go through this component.
 * Per CLAUDE.md §6: color is never the only signal — each level pairs a
 * distinct shape (circle / triangle / diamond / octagon), so the states
 * remain distinguishable under red-green colorblindness (~8% of men).
 */

const RISK_CONFIG: Record<
  RiskLevel,
  { label: string; colorVar: string; Icon: typeof CircleCheck; iconClassName?: string }
> = {
  SAFE: { label: 'Safe', colorVar: 'var(--color-risk-safe)', Icon: CircleCheck },
  CAUTION: { label: 'Caution', colorVar: 'var(--color-risk-caution)', Icon: AlertTriangle },
  HIGH: {
    label: 'High',
    colorVar: 'var(--color-risk-high)',
    Icon: Square,
    iconClassName: 'rotate-45',
  },
  CRITICAL: { label: 'Critical', colorVar: 'var(--color-risk-critical)', Icon: OctagonAlert },
}

interface RiskBadgeProps {
  level: RiskLevel
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

const SIZE_PX: Record<NonNullable<RiskBadgeProps['size']>, number> = {
  sm: 14,
  md: 18,
  lg: 24,
}

export function RiskBadge({ level, size = 'md', showLabel = true }: RiskBadgeProps) {
  const config = RISK_CONFIG[level]
  const px = SIZE_PX[size]

  return (
    <span
      className="inline-flex items-center gap-1.5 font-mono-data text-xs font-medium tracking-wide uppercase"
      style={{ color: config.colorVar }}
    >
      <config.Icon
        size={px}
        strokeWidth={2.25}
        className={config.iconClassName}
        aria-hidden="true"
      />
      {showLabel && <span>{config.label}</span>}
    </span>
  )
}

export function riskColor(level: RiskLevel): string {
  return RISK_CONFIG[level].colorVar
}

export function riskColorHex(level: RiskLevel): [number, number, number, number] {
  const hex: Record<RiskLevel, [number, number, number, number]> = {
    SAFE: [46, 125, 50, 200],
    CAUTION: [242, 201, 76, 200],
    HIGH: [255, 140, 0, 210],
    CRITICAL: [214, 40, 40, 230],
  }
  return hex[level]
}
