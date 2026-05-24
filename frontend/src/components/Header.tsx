import { motion } from 'motion/react'

export function Header() {
  return (
    <motion.header
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="relative z-10 border-b border-line"
    >
      <div className="mx-auto flex max-w-3xl items-center justify-between px-6 py-5">
        <div className="flex items-baseline gap-2.5">
          <span className="font-display text-2xl font-medium text-ink">
            Voyage
          </span>
          <span className="font-mono text-[10px] uppercase tracking-[0.28em] text-mute">
            travel concierge
          </span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.28em] text-mute">
          <span className="status-dot relative inline-block h-1.5 w-1.5 rounded-full bg-accent" />
          <span>online</span>
        </div>
      </div>
      <div className="scanline" aria-hidden="true" />
    </motion.header>
  )
}
