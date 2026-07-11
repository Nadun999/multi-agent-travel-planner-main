import { useState } from 'react'
import { motion } from 'motion/react'
import type { BookingForm } from '../types'

function isEmail(v: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
}

export function BookingFormCard({
  form,
  onSubmit,
}: {
  form: BookingForm
  onSubmit: (message: string) => void
}) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(form.fields.map((f) => [f.name, f.value ?? ''])),
  )
  const [submitted, setSubmitted] = useState(false)

  function setField(name: string, value: string) {
    setValues((prev) => ({ ...prev, [name]: value }))
  }

  const allFilled = form.fields.every((f) => values[f.name]?.trim())
  const emailsValid = form.fields
    .filter((f) => f.type === 'email')
    .every((f) => isEmail(values[f.name] ?? ''))
  const canSubmit = allFilled && emailsValid && !submitted

  function handleSubmit() {
    if (!canSubmit) return
    const summary = form.fields
      .map((f) => `${f.label}: ${values[f.name].trim()}`)
      .join(', ')
    setSubmitted(true)
    onSubmit(`Here are my booking details — ${summary}`)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className="w-full max-w-md overflow-hidden rounded-lg border border-line bg-card"
    >
      <div className="border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          <h3 className="font-display text-lg text-ink">{form.title}</h3>
        </div>
        <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
          Fill in the details to confirm
        </p>
      </div>

      <div className="space-y-3 px-4 py-4">
        {form.fields.map((field) => {
          const prefilled = !!field.value
          return (
            <div key={field.name}>
              <label className="mb-1 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-sub">
                {field.label}
                {prefilled && (
                  <span className="rounded-sm bg-accent/15 px-1.5 py-px text-[9px] text-accent">
                    detected
                  </span>
                )}
              </label>

              {field.type === 'select' ? (
                <div className="flex flex-wrap gap-1.5">
                  {(field.options ?? []).map((opt) => {
                    const active = values[field.name] === opt
                    return (
                      <button
                        key={opt}
                        type="button"
                        disabled={submitted}
                        onClick={() => setField(field.name, opt)}
                        className={[
                          'rounded-md border px-3 py-1.5 font-mono text-xs capitalize transition-colors',
                          active
                            ? 'border-accent/60 bg-accent/15 text-accent'
                            : 'border-line text-sub hover:border-line-strong',
                          submitted ? 'cursor-not-allowed opacity-60' : '',
                        ].join(' ')}
                      >
                        {opt}
                      </button>
                    )
                  })}
                </div>
              ) : (
                <input
                  type={field.type === 'email' ? 'email' : field.type === 'date' ? 'date' : 'text'}
                  value={values[field.name]}
                  disabled={submitted}
                  onChange={(e) => setField(field.name, e.target.value)}
                  placeholder={field.label}
                  className="w-full rounded-md border border-line bg-base px-3 py-2 text-sm text-ink placeholder:text-mute transition-colors focus:border-accent/50 focus:outline-none disabled:opacity-60"
                />
              )}
            </div>
          )
        })}
      </div>

      <div className="flex items-center justify-between border-t border-line px-4 py-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-mute">
          {submitted
            ? 'Submitted'
            : canSubmit
              ? 'Ready'
              : 'Complete all fields'}
        </span>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-md bg-accent px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.2em] text-void transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-line disabled:text-mute"
        >
          {submitted ? 'Submitted' : 'Review booking'}
        </button>
      </div>
    </motion.div>
  )
}
