import { useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { AnimatePresence, motion } from 'framer-motion'

/**
 * A styled tactical tooltip rendered through a portal to document.body,
 * so the top bar's own backdrop-filter (which creates a containing block
 * for fixed descendants) cannot clip it.
 *
 * The trigger is wrapped in an inline `.tooltip-wrap` span rather than
 * cloned, and disabled triggers get `pointer-events: none` (see
 * index.css) so a hover still reaches the wrapper: a tooltip on a
 * disabled control is exactly where "why is this unavailable?" needs
 * answering, and a disabled button otherwise swallows the hover.
 *
 * Pass either `label` + `hint` for the common two-line shape, or
 * `content` for anything richer.
 */
interface TooltipProps {
  label?: string
  hint?: string
  content?: ReactNode
  children: ReactNode
  delayMs?: number
}

export function Tooltip({ label, hint, content, children, delayMs = 180 }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null)
  const wrapRef = useRef<HTMLSpanElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const timer = useRef<number | undefined>(undefined)

  const show = () => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => setOpen(true), delayMs)
  }
  const hide = () => {
    window.clearTimeout(timer.current)
    setOpen(false)
    setPos(null)
  }

  // Measure the trigger and the tooltip once it has mounted, then clamp
  // the tooltip inside the viewport and flip it above the trigger if
  // there isn't room below. Runs before paint so there is no flash at
  // the wrong position (the tooltip stays invisible until `pos` is set).
  useLayoutEffect(() => {
    if (!open || !wrapRef.current || !tipRef.current) return
    const trigger = wrapRef.current.getBoundingClientRect()
    const tip = tipRef.current.getBoundingClientRect()
    const margin = 8
    const centerX = trigger.left + trigger.width / 2
    const left = Math.max(
      margin,
      Math.min(centerX - tip.width / 2, window.innerWidth - tip.width - margin),
    )
    let top = trigger.bottom + 8
    if (top + tip.height > window.innerHeight - margin) {
      top = trigger.top - tip.height - 8
    }
    setPos({ left, top })
  }, [open])

  const body = content ?? (
    <>
      {label && <div className="font-semibold text-[var(--color-text-primary)]">{label}</div>}
      {hint && <div className="mt-1 whitespace-pre-line">{hint}</div>}
    </>
  )

  return (
    <span
      ref={wrapRef}
      className="tooltip-wrap"
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
    >
      {children}
      {createPortal(
        <AnimatePresence>
          {open && (
            <motion.div
              ref={tipRef}
              role="tooltip"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: pos ? 1 : 0, y: 0 }}
              exit={{ opacity: 0, y: 4 }}
              transition={{ duration: 0.14, ease: 'easeOut' }}
              className="tactical-tooltip"
              style={{ left: pos?.left ?? -9999, top: pos?.top ?? -9999 }}
            >
              {body}
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </span>
  )
}
