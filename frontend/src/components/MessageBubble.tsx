import { motion } from 'motion/react'
import type { ChatMessage } from '../types'
import { BoardingPass } from './BoardingPass'
import { HotelKey } from './HotelKey'

export function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

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
        <div
          className={[
            'rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed',
            isUser
              ? 'bg-accent text-void'
              : 'text-ink',
          ].join(' ')}
        >
          <div className="whitespace-pre-wrap">{message.text}</div>
        </div>

        {message.flights && message.flights.length > 0 && (
          <div className="w-full max-w-xl space-y-2">
            {message.flights.map((f, i) => (
              <BoardingPass key={i} flight={f} index={i} />
            ))}
          </div>
        )}

        {message.hotels && message.hotels.length > 0 && (
          <div className="w-full max-w-xl space-y-2">
            {message.hotels.map((h, i) => (
              <HotelKey key={i} hotel={h} index={i} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

export function TypingBubble() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex justify-start"
    >
      <div className="flex items-center gap-1.5 px-4 py-2.5">
        <span
          className="h-1.5 w-1.5 rounded-full bg-accent"
          style={{
            animation: 'dot-flow 1.4s ease-in-out infinite',
            animationDelay: '0ms',
          }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full bg-accent"
          style={{
            animation: 'dot-flow 1.4s ease-in-out infinite',
            animationDelay: '180ms',
          }}
        />
        <span
          className="h-1.5 w-1.5 rounded-full bg-accent"
          style={{
            animation: 'dot-flow 1.4s ease-in-out infinite',
            animationDelay: '360ms',
          }}
        />
      </div>
    </motion.div>
  )
}
