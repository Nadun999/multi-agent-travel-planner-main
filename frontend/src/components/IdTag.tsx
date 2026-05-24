import { useState } from 'react'

/**
 * Booking reference shown on flight/hotel cards. Click copies the full
 * id so the user can paste it into a "book ..." chat message.
 */
export function IdTag({ id }: { id?: string }) {
  const [copied, setCopied] = useState(false)
  if (!id) return null

  const short = id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-3)}` : id

  async function copy() {
    try {
      await navigator.clipboard.writeText(id!)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      // clipboard unavailable — ignore
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      title={`Copy ID: ${id}`}
      className="group/id inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.2em] text-mute transition-colors hover:text-accent"
    >
      <span className="text-mute group-hover/id:text-accent">id</span>
      <span className="text-sub group-hover/id:text-accent">{short}</span>
      {copied ? (
        <svg
          viewBox="0 0 24 24"
          className="h-3 w-3 text-accent"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg
          viewBox="0 0 24 24"
          className="h-3 w-3 opacity-0 transition-opacity group-hover/id:opacity-100"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <rect x="9" y="9" width="11" height="11" rx="2" />
          <path d="M5 15V5a2 2 0 0 1 2-2h10" />
        </svg>
      )}
    </button>
  )
}
