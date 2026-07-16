import { useState } from 'react'
import { BookOpen, ChevronUp, Send } from 'lucide-react'
import { useCorrixStore } from '../store/useCorrixStore'

export function RegulatoryChatDrawer() {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const chatHistory = useCorrixStore((s) => s.chatHistory)
  const sendChatMessage = useCorrixStore((s) => s.sendChatMessage)

  return (
    <div
      className="glass-panel flex flex-col overflow-hidden transition-[height] duration-300"
      style={{ height: open ? 320 : 48 }}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-5 py-3 text-sm font-semibold text-[var(--color-text-primary)]"
      >
        <BookOpen size={16} aria-hidden="true" />
        Regulatory Intelligence
        <ChevronUp
          size={16}
          className={`ml-auto transition-transform ${open ? '' : 'rotate-180'}`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div className="flex min-h-0 flex-1 flex-col gap-3 px-5 pb-4">
          <div className="flex-1 overflow-y-auto flex flex-col gap-3 pr-1">
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
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
              </div>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!draft.trim()) return
              sendChatMessage(draft)
              setDraft('')
            }}
            className="flex items-center gap-2"
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Ask about OISD, Factories Act, or DGMS guidance…"
              className="flex-1 rounded-[var(--radius-control)] bg-white/[0.04] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none placeholder:text-[var(--color-text-secondary)]"
            />
            <button
              type="submit"
              className="rounded-[var(--radius-control)] p-2 text-[var(--color-accent)]"
              style={{ backgroundColor: 'color-mix(in srgb, var(--color-accent) 18%, transparent)' }}
              aria-label="Send"
            >
              <Send size={16} aria-hidden="true" />
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
