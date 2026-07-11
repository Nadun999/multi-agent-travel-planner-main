import { useState } from 'react'
import { motion } from 'motion/react'
import type { BookingReview } from '../types'

export function BookingReviewCard({
  review,
  onConfirm,
}: {
  review: BookingReview
  onConfirm: (message: string) => void
}) {
  const [confirmed, setConfirmed] = useState(false)

  function handleConfirm() {
    if (confirmed) return
    const summary = review.items
      .map((it) => `${it.label}: ${it.value ?? ''}`)
      .join(', ')
    setConfirmed(true)
    onConfirm(`Confirm and place the booking — ${summary}`)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="w-full max-w-md overflow-hidden rounded-lg border border-accent/30 bg-card"
    >
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <svg
            viewBox="0 0 24 24"
            className="h-4 w-4 text-accent"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path
              d="M9 12l2 2 4-4M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <h3 className="font-display text-lg text-ink">{review.title}</h3>
        </div>
        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
          Review the details, then confirm to finalize
        </p>
      </div>

      <dl className="divide-y divide-line">
        {review.items.map((it) => (
          <div
            key={it.label}
            className="flex items-baseline justify-between gap-4 px-4 py-2.5"
          >
            <dt className="font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
              {it.label}
            </dt>
            <dd className="text-right text-sm text-ink">{it.value ?? '—'}</dd>
          </div>
        ))}
      </dl>

      <div className="flex items-center justify-between border-t border-line px-4 py-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
          {confirmed ? 'Confirmed' : 'Not booked yet'}
        </span>
        <button
          type="button"
          onClick={handleConfirm}
          disabled={confirmed}
          className="rounded-md bg-accent px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.2em] text-void transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-line disabled:text-mute"
        >
          {confirmed ? 'Booked' : 'Confirm & book'}
        </button>
      </div>
    </motion.div>
  )
}
