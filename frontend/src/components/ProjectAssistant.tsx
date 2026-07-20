import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Loader2, MessageCircleQuestion, Send, Sparkles, X } from 'lucide-react'

/**
 * A floating "Ask about Corrix" assistant. A pill button in the bottom-right
 * opens a small chat that answers questions about the project (what it is,
 * how it works, what's real vs. simulated) via /api/assistant. Distinct from
 * the in-dashboard Regulatory Intelligence chat, which answers questions
 * about the regulations, not the product.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

interface Msg {
  id: string
  role: 'user' | 'assistant'
  text: string
}

const SUGGESTIONS = [
  'What is compound risk?',
  'What is real vs. simulated?',
  'How does the Safety Council work?',
]

export function ProjectAssistant() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<Msg[]>([
    { id: 'intro', role: 'assistant', text: 'Hi. Ask me anything about Corrix, what it does, how it works, or what is real vs. simulated.' },
  ])
  const [draft, setDraft] = useState('')
  const [pending, setPending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, pending])

  const send = async (text: string) => {
    const q = text.trim()
    if (!q || pending) return
    const userId = `u-${Date.now()}`
    setMessages((m) => [...m, { id: userId, role: 'user', text: q }])
    setDraft('')
    setPending(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/assistant`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      })
      if (!res.ok) throw new Error(String(res.status))
      const data: { answer: string } = await res.json()
      setMessages((m) => [...m, { id: `${userId}-a`, role: 'assistant', text: data.answer }])
    } catch {
      setMessages((m) => [
        ...m,
        { id: `${userId}-e`, role: 'assistant', text: 'I could not reach the backend to answer that. Confirm it is running, then try again.' },
      ])
    } finally {
      setPending(false)
    }
  }

  return (
    <>
      {/* Launcher */}
      <motion.button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-5 right-5 z-[70] flex items-center gap-2 rounded-full border px-4 py-3 text-sm font-medium shadow-lg"
        style={{
          borderColor: 'color-mix(in srgb, var(--color-accent) 50%, transparent)',
          background: 'linear-gradient(180deg, color-mix(in srgb, var(--color-accent) 22%, var(--color-surface-1)), var(--color-surface-1))',
          color: 'var(--color-accent)',
          boxShadow: '0 0 24px -6px color-mix(in srgb, var(--color-accent) 60%, transparent), var(--shadow-raised)',
        }}
        whileHover={{ y: -2 }}
        whileTap={{ scale: 0.96 }}
        aria-label="Ask about Corrix"
      >
        {open ? <X size={17} aria-hidden="true" /> : <MessageCircleQuestion size={17} aria-hidden="true" />}
        <span className="hidden sm:inline">{open ? 'Close' : 'Ask about Corrix'}</span>
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
            className="glass-panel corner-frame fixed bottom-20 right-5 z-[70] flex w-[min(380px,calc(100vw-2.5rem))] flex-col overflow-hidden"
            style={{ height: 'min(520px, calc(100vh - 8rem))' }}
          >
            {/* Header */}
            <div className="flex items-center gap-2 border-b border-[var(--color-hairline)] px-4 py-3">
              <Sparkles size={15} className="text-[var(--color-accent)]" aria-hidden="true" />
              <div className="flex flex-col leading-tight">
                <span className="font-display text-sm font-semibold text-[var(--color-text-primary)]">Ask about Corrix</span>
                <span className="eyebrow">Project assistant</span>
              </div>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="thin-scroll flex flex-1 flex-col gap-3 overflow-y-auto p-4">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`max-w-[88%] rounded-[var(--radius-control)] border px-3 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'self-end' : 'self-start'} text-[var(--color-text-primary)]`}
                  style={{
                    backgroundColor: m.role === 'user' ? 'var(--color-accent-dim)' : 'color-mix(in srgb, var(--color-surface-2) 70%, transparent)',
                    borderColor: m.role === 'user' ? 'color-mix(in srgb, var(--color-accent) 35%, transparent)' : 'var(--color-hairline)',
                  }}
                >
                  {m.text}
                </div>
              ))}
              {pending && (
                <div className="flex items-center gap-2 self-start rounded-[var(--radius-control)] border border-[var(--color-hairline)] px-3 py-2 text-sm text-[var(--color-text-secondary)]" style={{ backgroundColor: 'color-mix(in srgb, var(--color-surface-2) 70%, transparent)' }}>
                  <Loader2 size={13} className="animate-spin text-[var(--color-accent)]" aria-hidden="true" />
                  Thinking…
                </div>
              )}
              {messages.length === 1 && !pending && (
                <div className="mt-1 flex flex-col gap-1.5">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => send(s)}
                      className="self-start rounded-full border border-[var(--color-hairline)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] hover:text-[var(--color-text-primary)]"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Input */}
            <form
              onSubmit={(e) => { e.preventDefault(); send(draft) }}
              className="flex items-center gap-2 border-t border-[var(--color-hairline)] p-3"
            >
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={pending}
                placeholder="Ask anything about Corrix…"
                className="flex-1 rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] placeholder:text-[var(--color-text-tertiary)] disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={pending || !draft.trim()}
                className="rounded-[var(--radius-control)] border p-2 text-[var(--color-accent)] disabled:opacity-50"
                style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
                aria-label="Send"
              >
                <Send size={16} aria-hidden="true" />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
