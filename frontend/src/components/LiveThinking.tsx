import { AnimatePresence, motion } from 'motion/react'
import type { TraceStep } from '../types'
import { StepItem } from './ThinkingTrace'

/** Live progress shown while the graph is running — steps stream in as
 * each node finishes, with a trailing pulse for the work still in flight. */
export function LiveThinking({ steps }: { steps: TraceStep[] }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-xl rounded-lg border border-line bg-card/60"
    >
      <div className="flex items-center gap-2.5 px-3.5 py-2.5">
        <span className="status-dot relative inline-block h-2 w-2 rounded-full bg-accent" />
        <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-sub">
          Thinking
        </span>
        <span className="flex gap-1">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1 w-1 rounded-full bg-accent"
              style={{
                animation: 'dot-flow 1.4s ease-in-out infinite',
                animationDelay: `${i * 180}ms`,
              }}
            />
          ))}
        </span>
      </div>

      {steps.length > 0 && (
        <div className="border-t border-line px-3.5 py-3">
          <ol className="space-y-3">
            <AnimatePresence initial={false}>
              {steps.map((s, i) => (
                <motion.div
                  key={s.step}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                >
                  <StepItem
                    step={s}
                    isLast={i === steps.length - 1}
                    active={i === steps.length - 1}
                  />
                </motion.div>
              ))}
            </AnimatePresence>
          </ol>
        </div>
      )}
    </motion.div>
  )
}
