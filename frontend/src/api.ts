import type { ChatResponse, TraceStep } from './types'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/chat'
const STREAM_URL = `${API_URL}/stream`

export async function sendChat(message: string): Promise<ChatResponse> {
  const res = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  if (!res.ok) {
    throw new Error(`Backend error ${res.status}: ${res.statusText}`)
  }

  return (await res.json()) as ChatResponse
}

interface StreamHandlers {
  onStep: (step: TraceStep) => void
  onDone: (data: ChatResponse) => void
}

/**
 * Streams the agent run via Server-Sent Events. Each `step` event fires
 * onStep as a node finishes; the terminating `done` event carries the
 * final response, results, and full trace.
 */
export async function sendChatStream(
  message: string,
  { onStep, onDone }: StreamHandlers,
): Promise<void> {
  const res = await fetch(STREAM_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })

  if (!res.ok || !res.body) {
    throw new Error(`Backend error ${res.status}: ${res.statusText}`)
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const line = frame.trim()
      if (!line.startsWith('data:')) continue
      const json = line.slice(5).trim()
      if (!json) continue

      const evt = JSON.parse(json) as
        | { type: 'step'; step: TraceStep }
        | ({ type: 'done' } & ChatResponse)

      if (evt.type === 'step') {
        onStep(evt.step)
      } else if (evt.type === 'done') {
        const { type: _type, ...data } = evt
        void _type
        onDone(data)
      }
    }
  }
}
