import { motion } from 'motion/react'
import type { ChatMessage } from '../types'
import { BoardingPass } from './BoardingPass'
import { HotelKey } from './HotelKey'
import { ThinkingTrace } from './ThinkingTrace'
import { BookingFormCard } from './BookingFormCard'
import { BookingReviewCard } from './BookingReviewCard'

export function MessageBubble({
  message,
  onBookingSubmit,
}: {
  message: ChatMessage
  onBookingSubmit?: (message: string) => void
}) {
  const isUser = message.role === 'user'
  const hasForm = !isUser && !!message.bookingForm
  const hasReview = !isUser && !!message.bookingReview

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 320, damping: 30 }}
      className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`flex max-w-[88%] flex-col gap-3 ${
          isUser ? 'items-end' : 'items-start'
        }`}
      >
        {!isUser && message.trace && message.trace.length > 0 && (
          <ThinkingTrace trace={message.trace} />
        )}

        {hasForm ? (
          <BookingFormCard
            form={message.bookingForm!}
            onSubmit={(m) => onBookingSubmit?.(m)}
          />
        ) : hasReview ? (
          <BookingReviewCard
            review={message.bookingReview!}
            onConfirm={(m) => onBookingSubmit?.(m)}
          />
        ) : (
          <div
            className={[
              'rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed',
              isUser ? 'bg-accent text-void' : 'text-ink',
            ].join(' ')}
          >
            <div className="whitespace-pre-wrap">{message.text}</div>
          </div>
        )}

        {message.flights && message.flights.length > 0 && (
          <div className="w-full max-w-xl space-y-2">
            {message.flights.map((f, i) => (
              <BoardingPass
                key={i}
                flight={f}
                index={i}
                onBook={
                  onBookingSubmit
                    ? (id) => onBookingSubmit(`Book flight ${id}`)
                    : undefined
                }
              />
            ))}
          </div>
        )}

        {message.hotels && message.hotels.length > 0 && (
          <div className="w-full max-w-xl space-y-2">
            {message.hotels.map((h, i) => (
              <HotelKey
                key={i}
                hotel={h}
                index={i}
                onBook={
                  onBookingSubmit
                    ? (id) => onBookingSubmit(`Book hotel ${id}`)
                    : undefined
                }
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}
