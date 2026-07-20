import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ChevronDown } from 'lucide-react'

/**
 * A vertical scroll container that shows a "more below" affordance, a soft
 * bottom fade plus a gently-bouncing chevron, whenever its content extends
 * past the fold and the user hasn't scrolled to the bottom. Clicking the
 * chevron scrolls down by roughly a page. This exists because the right
 * sidebar (Council verdict + alert feed) grows below the fold when a
 * verdict lands, and people miss it without a scroll cue.
 */
export function ScrollColumn({ className, children }: { className?: string; children: ReactNode }) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [more, setMore] = useState(false)

  useEffect(() => {
    const scroller = scrollRef.current
    const content = contentRef.current
    if (!scroller || !content) return

    const update = () => {
      setMore(scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight > 24)
    }
    update()
    scroller.addEventListener('scroll', update, { passive: true })
    // Recompute when the content grows/shrinks (e.g. a verdict card appears)
    // or the viewport resizes.
    const ro = new ResizeObserver(update)
    ro.observe(content)
    ro.observe(scroller)
    window.addEventListener('resize', update)
    return () => {
      scroller.removeEventListener('scroll', update)
      ro.disconnect()
      window.removeEventListener('resize', update)
    }
  }, [])

  const scrollDown = () => {
    const el = scrollRef.current
    if (!el) return
    el.scrollBy({ top: el.clientHeight * 0.7, behavior: 'smooth' })
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div ref={scrollRef} className={className}>
        <div ref={contentRef} className="flex flex-col gap-2.5">
          {children}
        </div>
      </div>

      <AnimatePresence>
        {more && (
          <>
            {/* soft fade so cut-off content reads as continuing */}
            <motion.div
              key="fade"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="pointer-events-none absolute inset-x-0 bottom-0 h-14 rounded-b-[var(--radius-panel)]"
              style={{ background: 'linear-gradient(to top, var(--color-base), transparent)' }}
              aria-hidden="true"
            />
            {/* chevron cue */}
            <motion.button
              key="chevron"
              type="button"
              onClick={scrollDown}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              transition={{ duration: 0.2 }}
              className="absolute bottom-2 left-1/2 z-10 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border"
              style={{
                borderColor: 'color-mix(in srgb, var(--color-accent) 50%, transparent)',
                background: 'color-mix(in srgb, var(--color-surface-1) 92%, transparent)',
                color: 'var(--color-accent)',
                boxShadow: '0 0 18px -4px color-mix(in srgb, var(--color-accent) 60%, transparent), var(--shadow-raised)',
              }}
              aria-label="Scroll down for more"
              title="More below"
            >
              <motion.span
                animate={{ y: [0, 3, 0] }}
                transition={{ duration: 1.3, repeat: Infinity, ease: 'easeInOut' }}
                style={{ display: 'grid', placeItems: 'center' }}
              >
                <ChevronDown size={17} aria-hidden="true" />
              </motion.span>
            </motion.button>
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
