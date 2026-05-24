import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { sendChat } from './api'
import type { ChatMessage } from './types'
import { Header } from './components/Header'
import { MessageBubble, TypingBubble } from './components/MessageBubble'
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
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages, loading])

  async function handleSend() {
    const text = input.trim()
    if (!text || loading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      text,
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await sendChat(text)
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          text: data.response ?? 'No response returned.',
          flights: data.flights ?? undefined,
          hotels: data.hotels ?? undefined,
        },
      ])
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
    }
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
                <MessageBubble key={m.id} message={m} />
              ))}
            </AnimatePresence>
          )}

          {loading && <TypingBubble />}
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
