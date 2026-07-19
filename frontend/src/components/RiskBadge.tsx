import { AlertTriangle, CircleCheck, OctagonAlert, Square } from 'lucide-react'
import { motion } from 'framer-motion'
import type { RiskLevel } from '../types'

/**
 * Every risk-state indicator in the app must go through this component.
 * Per CLAUDE.md §6: color is never the only signal; each level pairs a
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
      <motion.span
        key={level}
        className="inline-flex"
        initial={{ scale: 0.4, opacity: 0, rotate: -20 }}
        animate={{ scale: 1, opacity: 1, rotate: 0 }}
        transition={{ type: 'spring', stiffness: 480, damping: 14 }}
      >
        <config.Icon
          size={px}
          strokeWidth={2.25}
          className={config.iconClassName}
          aria-hidden="true"
        />
      </motion.span>
      {showLabel && (
        <motion.span
          key={`${level}-label`}
          initial={{ opacity: 0, x: -4 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.2 }}
        >
          {config.label}
        </motion.span>
      )}
    </span>
  )
}

export function riskColor(level: RiskLevel): string {
  return RISK_CONFIG[level].colorVar
}

/** The pure, saturated risk hue (for borders, glyphs, route). Matches the
 * --color-risk-* tokens. */
export function riskColorHex(level: RiskLevel): [number, number, number, number] {
  const hex: Record<RiskLevel, [number, number, number, number]> = {
    SAFE: [51, 201, 139, 235],
    CAUTION: [245, 195, 59, 235],
    HIGH: [255, 138, 61, 240],
    CRITICAL: [255, 61, 81, 245],
  }
  return hex[level]
}

/** The map ZONE FILL, deliberately different from the badge hue: a
 * nominal (SAFE) zone is dark graphite so the plant reads calm by
 * default and only risk lights up. Risk zones get a translucent wash of
 * their hue over that dark base, brightening with severity. */
export function zoneFillHex(level: RiskLevel): [number, number, number, number] {
  const fill: Record<RiskLevel, [number, number, number, number]> = {
    SAFE: [24, 34, 45, 235],
    CAUTION: [92, 74, 30, 240],
    HIGH: [110, 60, 26, 245],
    CRITICAL: [120, 32, 42, 250],
  }
  return fill[level]
}
