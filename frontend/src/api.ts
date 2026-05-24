import type { ChatResponse } from './types'

const API_URL =
  import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/chat'

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
