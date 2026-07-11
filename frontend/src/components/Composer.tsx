import { useRef } from 'react'
import { motion } from 'motion/react'
import { useLiquidGlass } from '../hooks/useLiquidGlass'

interface Props {
  value: string
  loading: boolean
  onChange: (v: string) => void
  onSend: () => void
}

export function Composer({ value, loading, onChange, onSend }: Props) {
  const glassRef = useRef<HTMLDivElement>(null)
  useLiquidGlass(glassRef, {
    scale: -80,
    chroma: 5,
    blur: 4,
    saturate: 1.6,
    border: 0.08,
  })

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  const canSend = !loading && value.trim().length > 0

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, delay: 0.15, ease: [0.16, 1, 0.3, 1] }}
      className="relative z-10"
    >
      <div className="mx-auto w-full max-w-3xl px-6 py-4">
        <div
          ref={glassRef}
          className="glass group relative flex items-end gap-3 rounded-2xl px-4 py-3 transition-all focus-within:border-accent/50 focus-within:shadow-[0_0_32px_-8px_rgba(94,234,212,0.35)]"
        >
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKey}
            rows={1}
            placeholder="Where to?"
            className="block flex-1 resize-none bg-transparent text-[15px] text-ink placeholder:text-mute focus:outline-none"
          />
          <motion.button
            type="button"
            onClick={onSend}
            disabled={!canSend}
            aria-label="Send"
            whileTap={{ scale: 0.92 }}
            className={[
              'relative flex h-9 w-9 items-center justify-center rounded-full transition-all',
              canSend
                ? 'bg-accent text-void hover:shadow-[0_0_24px_-4px_rgba(94,234,212,0.6)]'
                : 'bg-line text-mute cursor-not-allowed',
            ].join(' ')}
          >
            {loading ? (
              <svg
                viewBox="0 0 24 24"
                className="spin h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M12 3a9 9 0 1 1-6.4 2.6"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <svg
                viewBox="0 0 24 24"
                className="h-4 w-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path
                  d="M5 12h14M13 6l6 6-6 6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </motion.button>
        </div>
      </div>
    </motion.div>
  )
}
