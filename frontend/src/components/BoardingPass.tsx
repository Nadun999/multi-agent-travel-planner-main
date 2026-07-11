import type { Flight } from '../types'
import { motion } from 'motion/react'
import { IdTag } from './IdTag'

function airportCode(airport?: string) {
  if (!airport) return '—'
  const upper = airport.toUpperCase()
  return upper.length > 3 ? upper.slice(0, 3) : upper
}

export function BoardingPass({
  flight,
  index = 0,
  onBook,
}: {
  flight: Flight
  index?: number
  onBook?: (id: string) => void
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        type: 'spring',
        stiffness: 320,
        damping: 28,
        delay: 0.05 * index,
      }}
      whileHover={{ y: -2 }}
      className="group relative overflow-hidden rounded-lg border border-line bg-card p-5 transition-colors hover:border-line-strong"
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px scale-x-0 bg-gradient-to-r from-transparent via-accent to-transparent transition-transform duration-500 group-hover:scale-x-100" />

      <div className="flex items-baseline justify-between gap-6">
        <div className="flex items-baseline gap-3">
          <span className="font-display text-3xl font-medium text-ink">
            {airportCode(flight.origin?.airport)}
          </span>
          <motion.span
            initial={{ x: -4, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ delay: 0.05 * index + 0.15 }}
            className="text-accent"
          >
            →
          </motion.span>
          <span className="font-display text-3xl font-medium text-ink">
            {airportCode(flight.destination?.airport)}
          </span>
        </div>
        <div className="text-right font-mono text-sm font-medium text-accent">
          {flight.currency} {flight.price}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-sub">
        <span>
          {flight.airline} {flight.flightNumber}
        </span>
        <span className="text-mute">·</span>
        <span>{flight.flightDate}</span>
        <span className="text-mute">·</span>
        <span>
          {flight.departureTime} – {flight.arrivalTime}
        </span>
        {flight.availableSeats !== undefined && (
          <>
            <span className="text-mute">·</span>
            <span>{flight.availableSeats} seats</span>
          </>
        )}
      </div>

      {flight._id && (
        <div className="mt-3 flex items-center justify-between border-t border-line pt-2.5">
          <IdTag id={flight._id} />
          {onBook && (
            <button
              type="button"
              onClick={() => onBook(flight._id!)}
              className="rounded-md border border-accent/40 bg-accent/10 px-3 py-1 font-mono text-[10px] uppercase tracking-[0.2em] text-accent transition-colors hover:bg-accent/20"
            >
              Book
            </button>
          )}
        </div>
      )}
    </motion.div>
  )
}
