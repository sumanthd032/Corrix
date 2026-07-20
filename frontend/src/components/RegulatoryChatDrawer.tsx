import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BookOpen, ChevronUp, MessageCircleQuestion, Send, X } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

const NUDGE_FLAG = 'corrix_reg_nudge_dismissed'
const TOUR_FLAG = 'corrix_tour_shown'

export function RegulatoryChatDrawer() {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [showNudge, setShowNudge] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const chatHistory = useCorrixStore((s) => s.chatHistory)
  const chatPending = useCorrixStore((s) => s.chatPending)
  const sendChatMessage = useCorrixStore((s) => s.sendChatMessage)

  // A one-time contextual nudge pointing at this feature, shown a few
  // seconds after onboarding finishes (so it doesn't collide with the
  // guided tour) and auto-hidden after a while. Dismissed for the session
  // once seen or acted on.
  useEffect(() => {
    if (sessionStorage.getItem(NUDGE_FLAG)) return
    let hideTimer: ReturnType<typeof setTimeout> | null = null
    const poll = setInterval(() => {
      // wait until the guided tour has run (or been skipped) and the drawer
      // is still closed and untouched
      if (!sessionStorage.getItem(TOUR_FLAG)) return
      clearInterval(poll)
      const showTimer = setTimeout(() => {
        setShowNudge((prev) => {
          if (sessionStorage.getItem(NUDGE_FLAG)) return prev
          return true
        })
        hideTimer = setTimeout(() => setShowNudge(false), 13000)
      }, 2500)
      // ensure showTimer is cleared if unmounted before it fires
      hideTimer = showTimer
    }, 1000)
    return () => {
      clearInterval(poll)
      if (hideTimer) clearTimeout(hideTimer)
    }
  }, [])

  const dismissNudge = () => {
    sessionStorage.setItem(NUDGE_FLAG, '1')
    setShowNudge(false)
  }

  // Once the drawer is opened by any means, the user has found the feature;
  // never nudge them about it again this session.
  useEffect(() => {
    if (open) {
      sessionStorage.setItem(NUDGE_FLAG, '1')
      setShowNudge(false)
    }
  }, [open])

  const openFromNudge = () => {
    dismissNudge()
    setOpen(true)
    setTimeout(() => inputRef.current?.focus(), 350)
  }

  return (
    <motion.div
      className="glass-panel relative flex flex-col overflow-visible"
      data-tour="regulatory"
      animate={{ height: open ? 320 : 48 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      {/* Contextual nudge */}
      <AnimatePresence>
        {showNudge && !open && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.97 }}
            transition={{ type: 'spring', stiffness: 320, damping: 24 }}
            className="absolute bottom-[54px] left-4 z-30 w-[300px]"
          >
            <div
              className="glass-panel flex items-start gap-3 p-3.5"
              style={{ boxShadow: '0 0 26px -8px color-mix(in srgb, var(--color-accent) 60%, transparent), var(--shadow-raised)' }}
            >
              <div
                className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-control)]"
                style={{ background: 'var(--color-accent-dim)' }}
              >
                <MessageCircleQuestion size={17} className="text-[var(--color-accent)]" aria-hidden="true" />
              </div>
              <div className="flex flex-col gap-2">
                <div>
                  <p className="text-sm font-semibold text-[var(--color-text-primary)]">Have a compliance question?</p>
                  <p className="mt-0.5 text-xs leading-relaxed text-[var(--color-text-secondary)]">
                    Ask the OISD, Factories Act, and DGMS regulations directly and get answers with real clause citations.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={openFromNudge}
                  className="self-start rounded-[var(--radius-control)] border px-3 py-1.5 text-xs font-medium text-[var(--color-accent)]"
                  style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
                >
                  Ask a question
                </button>
              </div>
              <button
                type="button"
                onClick={dismissNudge}
                className="ml-auto -mr-1 -mt-1 shrink-0 rounded-[var(--radius-control)] p-1 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-secondary)]"
                aria-label="Dismiss"
              >
                <X size={14} aria-hidden="true" />
              </button>
            </div>
            {/* pointer */}
            <div
              className="absolute -bottom-1 left-6 h-3 w-3 rotate-45 border-b border-r"
              style={{ background: 'color-mix(in srgb, var(--color-surface-1) 92%, transparent)', borderColor: 'var(--color-hairline)' }}
              aria-hidden="true"
            />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        type="button"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ backgroundColor: 'color-mix(in srgb, var(--color-surface-3) 40%, transparent)' }}
        className="flex items-center gap-2 px-4 py-3 text-sm font-semibold text-[var(--color-text-primary)]"
      >
        <BookOpen size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
        Regulatory Intelligence
        <span className="eyebrow ml-2 hidden sm:inline">OISD · Factories Act · DGMS</span>
        <motion.span
          className="ml-auto"
          animate={{ rotate: open ? 0 : 180 }}
          transition={{ duration: 0.25 }}
        >
          <ChevronUp size={16} className="text-[var(--color-text-tertiary)]" aria-hidden="true" />
        </motion.span>
      </motion.button>

      {open && (
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-4 pb-4">
          <div className="thin-scroll flex-1 overflow-y-auto flex flex-col gap-3 pr-1">
            <AnimatePresence initial={false}>
              {chatHistory.map((msg, i) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: Math.min(i * 0.04, 0.3) }}
                  className={`max-w-[85%] rounded-[var(--radius-control)] border px-3 py-2 text-sm leading-relaxed ${
                    msg.role === 'user' ? 'self-end' : 'self-start'
                  } text-[var(--color-text-primary)]`}
                  style={{
                    backgroundColor:
                      msg.role === 'user'
                        ? 'var(--color-accent-dim)'
                        : 'color-mix(in srgb, var(--color-surface-2) 70%, transparent)',
                    borderColor:
                      msg.role === 'user'
                        ? 'color-mix(in srgb, var(--color-accent) 35%, transparent)'
                        : 'var(--color-hairline)',
                  }}
                >
                  <p>{msg.text}</p>
                  {msg.citations?.map((c) => (
                    <p
                      key={c.sectionNumber}
                      className="mt-1.5 flex items-center gap-1.5 tnum text-[11px] text-[var(--color-accent)]"
                    >
                      {c.isSupplementary && (
                        <span className="text-[var(--color-risk-caution)]">[supp]</span>
                      )}
                      {c.sourceDocument} §{c.sectionNumber}
                    </p>
                  ))}
                </motion.div>
              ))}
              {chatPending && (
                <motion.div
                  key="chat-pending"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="max-w-[85%] self-start rounded-[var(--radius-control)] px-3 py-2 text-sm text-[var(--color-text-secondary)]"
                  style={{ backgroundColor: 'rgba(255,255,255,0.04)' }}
                >
                  Searching the regulatory corpus…
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!draft.trim() || chatPending) return
              sendChatMessage(draft)
              setDraft('')
            }}
            className="flex items-center gap-2"
          >
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about OISD, Factories Act, or DGMS guidance…"
              disabled={chatPending}
              className="flex-1 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] placeholder:text-[var(--color-text-tertiary)] disabled:opacity-50"
            />
            <motion.button
              type="submit"
              disabled={chatPending || !draft.trim()}
              whileHover={{ scale: chatPending ? 1 : 1.06 }}
              whileTap={{ scale: chatPending ? 1 : 0.92 }}
              className="rounded-[var(--radius-control)] border p-2 text-[var(--color-accent)] disabled:opacity-50"
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
              aria-label="Send"
            >
              <Send size={16} aria-hidden="true" />
            </motion.button>
          </form>
        </div>
      )}
    </motion.div>
  )
}
