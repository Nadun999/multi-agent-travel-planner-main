import type { Hotel } from '../types'
import { motion } from 'motion/react'
import { IdTag } from './IdTag'

export function HotelKey({
  hotel,
  index = 0,
}: {
  hotel: Hotel
  index?: number
}) {
  const city = hotel.city ?? hotel.location?.city ?? ''
  const price = hotel.pricePerNight ?? hotel.price ?? hotel.currency ?? ''

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

      <div className="flex items-baseline justify-between gap-4">
        <div className="font-display text-2xl italic text-ink">
          {hotel.name ?? 'Unknown Property'}
        </div>
        {price && (
          <div className="font-mono text-sm font-medium text-accent whitespace-nowrap">
            {price}
          </div>
        )}
      </div>
      {city && (
        <div className="mt-1.5 font-mono text-[11px] text-sub">{city}</div>
      )}

      {hotel._id && (
        <div className="mt-3 border-t border-line pt-2.5">
          <IdTag id={hotel._id} />
        </div>
      )}
    </motion.div>
  )
}
