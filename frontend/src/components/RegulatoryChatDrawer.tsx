import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BookOpen, ChevronUp, Send } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

export function RegulatoryChatDrawer() {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const chatHistory = useCorrixStore((s) => s.chatHistory)
  const chatPending = useCorrixStore((s) => s.chatPending)
  const sendChatMessage = useCorrixStore((s) => s.sendChatMessage)

  return (
    <motion.div
      className="glass-panel flex flex-col overflow-hidden"
      animate={{ height: open ? 320 : 48 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <motion.button
        type="button"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ backgroundColor: 'rgba(255,255,255,0.02)' }}
        className="flex items-center gap-2 px-5 py-3 text-sm font-semibold text-[var(--color-text-primary)]"
      >
        <BookOpen size={16} aria-hidden="true" />
        Regulatory Intelligence
        <motion.span
          className="ml-auto"
          animate={{ rotate: open ? 0 : 180 }}
          transition={{ duration: 0.25 }}
        >
          <ChevronUp size={16} aria-hidden="true" />
        </motion.span>
      </motion.button>

      {open && (
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-5 pb-4">
          <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1">
            <AnimatePresence initial={false}>
              {chatHistory.map((msg, i) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.25, delay: Math.min(i * 0.04, 0.3) }}
                  className={`max-w-[85%] rounded-[var(--radius-control)] px-3 py-2 text-sm ${
                    msg.role === 'user' ? 'self-end text-[var(--color-text-primary)]' : 'self-start text-[var(--color-text-primary)]'
                  }`}
                  style={{
                    backgroundColor:
                      msg.role === 'user'
                        ? 'color-mix(in srgb, var(--color-accent) 18%, transparent)'
                        : 'rgba(255,255,255,0.04)',
                  }}
                >
                  <p>{msg.text}</p>
                  {msg.citations?.map((c) => (
                    <p
                      key={c.sectionNumber}
                      className="mt-1.5 font-mono-data text-[11px] text-[var(--color-text-secondary)]"
                    >
                      {c.isSupplementary && (
                        <span className="mr-1 text-[var(--color-risk-caution)]">[supplementary]</span>
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
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about OISD, Factories Act, or DGMS guidance…"
              disabled={chatPending}
              className="flex-1 rounded-[var(--radius-control)] bg-white/[0.04] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-secondary)] disabled:opacity-50"
            />
            <motion.button
              type="submit"
              disabled={chatPending || !draft.trim()}
              whileHover={{ scale: chatPending ? 1 : 1.06 }}
              whileTap={{ scale: chatPending ? 1 : 0.92 }}
              className="rounded-[var(--radius-control)] p-2 text-[var(--color-accent)] disabled:opacity-50"
              style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 18%, transparent)' }}
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
