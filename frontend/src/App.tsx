import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { sendChatStream } from './api'
import type { ChatMessage, TraceStep } from './types'
import { Header } from './components/Header'
import { MessageBubble } from './components/MessageBubble'
import { LiveThinking } from './components/LiveThinking'
import { Composer } from './components/Composer'
import { RippleCanvas } from './components/RippleCanvas'

function EmptyState() {
  const lines = [
    { plain: 'Where would you', italic: '' },
    { plain: '', italic: 'like to go?' },
  ]

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.08, delayChildren: 0.1 } },
      }}
      className="mx-auto flex max-w-xl flex-col items-start gap-4 py-24"
    >
      <motion.div
        variants={{
          hidden: { opacity: 0, y: 8 },
          visible: { opacity: 1, y: 0 },
        }}
        className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.3em] text-mute"
      >
        <span className="h-px w-6 bg-line-strong" />
        <span>session 01</span>
      </motion.div>

      <h1 className="font-display text-5xl font-light leading-[1.05] tracking-tight text-ink md:text-6xl">
        {lines.map((line, i) => (
          <motion.span
            key={i}
            variants={{
              hidden: { opacity: 0, y: 12, filter: 'blur(8px)' },
              visible: { opacity: 1, y: 0, filter: 'blur(0px)' },
            }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
            className="block"
          >
            {line.plain}{' '}
            {line.italic && (
              <span className="italic text-accent">{line.italic}</span>
            )}
            {i === lines.length - 1 && <span className="caret">&nbsp;</span>}
          </motion.span>
        ))}
      </h1>

      <motion.p
        variants={{
          hidden: { opacity: 0, y: 8 },
          visible: { opacity: 1, y: 0 },
        }}
        className="font-sans text-base text-sub"
      >
        Ask in plain language. Flights, hotels, or full itineraries.
      </motion.p>
    </motion.div>
  )
}

function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [liveTrace, setLiveTrace] = useState<TraceStep[]>([])
  const [liveText, setLiveText] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, loading, liveTrace, liveText])

  async function send(text: string) {
    if (!text || loading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    setLiveTrace([])
    setLiveText('')

    try {
      await sendChatStream(text, {
        onStep: (step) => setLiveTrace((prev) => [...prev, step]),
        onToken: (t) => setLiveText((prev) => prev + t),
        onDone: (data) =>
          setMessages((prev) => [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: 'assistant',
              text: data.response ?? 'No response returned.',
              flights: data.flights ?? undefined,
              hotels: data.hotels ?? undefined,
              trace: data.trace ?? undefined,
              bookingForm: data.booking_form ?? undefined,
              bookingReview: data.booking_review ?? undefined,
            },
          ]),
      })
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: err instanceof Error ? err.message : 'Unknown error.',
        },
      ])
    } finally {
      setLoading(false)
      setLiveTrace([])
      setLiveText('')
    }
  }

  function handleSend() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    void send(text)
  }

  return (
    <div className="relative flex h-full flex-col">
      <div className="ambient" aria-hidden="true" />
      <RippleCanvas />

      <Header />

      <main
        ref={scrollRef}
        className="chat-scroll relative z-10 flex-1 overflow-y-auto"
      >
        <div className="mx-auto w-full max-w-3xl px-6 py-6 space-y-4">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <AnimatePresence initial={false}>
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} onBookingSubmit={send} />
              ))}
            </AnimatePresence>
          )}

          {loading && (
            <div className="flex flex-col gap-3">
              <div className="flex justify-start">
                <LiveThinking steps={liveTrace} />
              </div>

              {liveText && (
                <div className="flex justify-start">
                  <div className="max-w-[88%] rounded-2xl px-4 py-2.5 text-[15px] leading-relaxed text-ink">
                    <div className="whitespace-pre-wrap">
                      {liveText}
                      <span className="caret">&nbsp;</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      <Composer
        value={input}
        loading={loading}
        onChange={setInput}
        onSend={handleSend}
      />
    </div>
  )
}

export default App
