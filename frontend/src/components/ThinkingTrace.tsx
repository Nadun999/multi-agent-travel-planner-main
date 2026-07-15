import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { TraceStep } from '../types'
import { useLiquidGlass } from '../hooks/useLiquidGlass'

export const NODE_BADGES: Record<string, string> = {
  input: 'input',
  router: 'route',
  hotel_node: 'hotel',
  flight_node: 'flight',
  general_qa_node: 'general',
  unknown_node: 'general',
  generate_response: 'compose',
}

function humanize(key: string) {
  return key.replace(/_/g, ' ')
}

function renderValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function ValueCell({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return (
      <span className="flex flex-col gap-0.5 text-accent">
        {value.map((v, i) => (
          <span key={i} className="break-words">
            {renderValue(v)}
          </span>
        ))}
      </span>
    )
  }
  if (value !== null && typeof value === 'object') {
    return (
      <span className="flex flex-wrap gap-x-3 gap-y-0.5 text-sub">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <span key={k}>
            <span className="text-mute">{humanize(k)}=</span>
            <span className="text-accent">{renderValue(v)}</span>
          </span>
        ))}
      </span>
    )
  }
  return <span className="break-words text-accent">{renderValue(value)}</span>
}

export function DetailRows({ detail }: { detail: Record<string, unknown> }) {
  const entries = Object.entries(detail)
  if (entries.length === 0) return null

  return (
    <div className="mt-2 space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex gap-2 font-mono text-[11px] leading-relaxed">
          <span className="shrink-0 text-mute">{humanize(key)}</span>
          <ValueCell value={value} />
        </div>
      ))}
    </div>
  )
}

export function StepItem({
  step,
  isLast,
  active = false,
}: {
  step: TraceStep
  isLast: boolean
  active?: boolean
}) {
  return (
    <li className="relative pl-5">
      <span
        className={`absolute left-0 top-1 h-2 w-2 rounded-full bg-accent ${
          active ? 'status-dot' : ''
        }`}
      />
      {!isLast && (
        <span className="absolute left-[3px] top-3.5 bottom-[-12px] w-px bg-line-strong" />
      )}

      <div className="flex items-baseline gap-2">
        <span className="text-[13px] text-ink">{step.title}</span>
        <span className="rounded-sm bg-card-2 px-1.5 py-px font-mono text-[9px] uppercase tracking-[0.2em] text-mute">
          {NODE_BADGES[step.node] ?? step.node}
        </span>
        {step.duration_ms > 0 && (
          <span className="ml-auto font-mono text-[10px] text-mute">
            {step.duration_ms}ms
          </span>
        )}
      </div>

      <DetailRows detail={step.detail} />
    </li>
  )
}

export function ThinkingTrace({ trace }: { trace?: TraceStep[] }) {
  const [open, setOpen] = useState(false)
  const glassRef = useRef<HTMLDivElement>(null)
  useLiquidGlass(glassRef, { scale: -70, chroma: 4, blur: 3, saturate: 1.5 })

  if (!trace || trace.length === 0) return null

  const totalMs = trace.reduce((sum, s) => sum + (s.duration_ms || 0), 0)
  const totalLabel =
    totalMs >= 1000 ? `${(totalMs / 1000).toFixed(1)}s` : `${totalMs}ms`

  return (
    <div
      ref={glassRef}
      className="glass w-full max-w-xl overflow-hidden rounded-lg"
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2.5 px-3.5 py-2.5 text-left transition-colors hover:bg-card-2/60"
      >
        <svg
          viewBox="0 0 24 24"
          className="h-3.5 w-3.5 shrink-0 text-accent"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path
            d="M12 3a4 4 0 0 1 4 4 4 4 0 0 1 0 8 4 4 0 0 1-8 0 4 4 0 0 1 0-8 4 4 0 0 1 4-4z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M12 7v10" strokeLinecap="round" />
        </svg>
        <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-sub">
          Thought for {totalLabel}
        </span>
        <span className="font-mono text-[11px] uppercase tracking-[0.22em] text-mute">
          · {trace.length} steps
        </span>
        <motion.svg
          viewBox="0 0 24 24"
          className="ml-auto h-3.5 w-3.5 text-mute"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          animate={{ rotate: open ? 180 : 0 }}
          transition={{ duration: 0.2 }}
        >
          <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </motion.svg>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="border-t border-line px-3.5 py-3">
              <ol className="space-y-3">
                {trace.map((s, i) => (
                  <StepItem key={s.step} step={s} isLast={i === trace.length - 1} />
                ))}
              </ol>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
