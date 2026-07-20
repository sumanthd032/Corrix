import { useState } from 'react'
import { createPortal } from 'react-dom'
import { motion } from 'framer-motion'
import { CheckCircle2, Loader2, Mail, X } from 'lucide-react'
import type { CouncilVerdict } from '../types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const EMAIL_KEY = 'corrix_alert_email'

type State =
  | { status: 'idle' }
  | { status: 'sending' }
  | { status: 'sent'; toEmail: string; hash: string }
  | { status: 'error'; message: string }

const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s.trim())

export function SendAlertModal({ verdict, onClose }: { verdict: CouncilVerdict; onClose: () => void }) {
  const [email, setEmail] = useState(() => localStorage.getItem(EMAIL_KEY) ?? '')
  const [state, setState] = useState<State>({ status: 'idle' })

  const send = async () => {
    if (!isEmail(email) || state.status === 'sending') return
    setState({ status: 'sending' })
    try {
      const res = await fetch(`${API_BASE_URL}/api/send-alert`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ verdict, toEmail: email.trim() }),
      })
      const data = await res.json()
      if (!data.ok) {
        setState({ status: 'error', message: data.error ?? 'The alert could not be sent.' })
        return
      }
      localStorage.setItem(EMAIL_KEY, email.trim())
      setState({ status: 'sent', toEmail: data.toEmail, hash: data.evidenceHash })
    } catch {
      setState({ status: 'error', message: 'Could not reach the backend to send the alert. Confirm it is running.' })
    }
  }

  return createPortal(
    <motion.div
      className="fixed inset-0 z-[95] flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      <motion.div
        className="glass-panel corner-frame w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.95, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        role="dialog"
        aria-label="Send email alert"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail size={16} className="text-[var(--color-accent)]" aria-hidden="true" />
            <h2 className="font-display text-base font-semibold text-[var(--color-text-primary)]">Send email alert</h2>
          </div>
          <button type="button" onClick={onClose} className="rounded-[var(--radius-control)] p-1 text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]" aria-label="Close">
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {state.status === 'sent' ? (
          <div className="mt-4 flex flex-col items-center gap-3 py-4 text-center">
            <CheckCircle2 size={34} style={{ color: 'var(--color-risk-safe)' }} aria-hidden="true" />
            <p className="text-sm text-[var(--color-text-primary)]">
              Alert sent to <span className="font-medium text-[var(--color-accent)]">{state.toEmail}</span>.
            </p>
            <p className="break-all tnum text-[11px] text-[var(--color-text-tertiary)]">
              Evidence hash (SHA-256): {state.hash}
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-1 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)]"
              style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
            >
              Done
            </button>
          </div>
        ) : (
          <>
            <p className="mt-3 text-sm leading-relaxed text-[var(--color-text-secondary)]">
              Send this {verdict.riskLevel} compound-risk verdict for Zone {verdict.zoneId} as a real email, with a
              tamper-evident hashed evidence snapshot and the evacuation route attached.
            </p>

            <label className="mt-4 block">
              <span className="eyebrow">Recipient email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') send() }}
                placeholder="safety.officer@example.com"
                disabled={state.status === 'sending'}
                className="mt-1.5 w-full rounded-[var(--radius-control)] border border-[var(--color-hairline)] bg-[var(--color-surface-2)]/60 px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-colors focus:border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] placeholder:text-[var(--color-text-tertiary)] disabled:opacity-50"
                autoFocus
              />
            </label>

            {state.status === 'error' && (
              <p className="mt-3 rounded-[var(--radius-control)] border px-3 py-2 text-xs" style={{ borderColor: 'color-mix(in srgb, var(--color-risk-critical) 45%, transparent)', color: 'var(--color-risk-critical)' }}>
                {state.message}
              </p>
            )}

            <div className="mt-5 flex items-center justify-end gap-2">
              <button type="button" onClick={onClose} className="rounded-[var(--radius-control)] px-3 py-2 text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
                Cancel
              </button>
              <button
                type="button"
                onClick={send}
                disabled={!isEmail(email) || state.status === 'sending'}
                className="flex items-center gap-1.5 rounded-[var(--radius-control)] border px-4 py-2 text-sm font-medium text-[var(--color-accent)] disabled:opacity-40"
                style={{ borderColor: 'color-mix(in srgb, var(--color-accent) 45%, transparent)', backgroundColor: 'var(--color-accent-dim)' }}
              >
                {state.status === 'sending' ? <Loader2 size={15} className="animate-spin" aria-hidden="true" /> : <Mail size={15} aria-hidden="true" />}
                {state.status === 'sending' ? 'Sending…' : 'Send alert'}
              </button>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>,
    document.body,
  )
}
