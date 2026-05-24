export interface Flight {
  _id?: string
  airline?: string
  flightNumber?: string
  origin?: { airport?: string }
  destination?: { airport?: string }
  flightDate?: string
  departureTime?: string
  arrivalTime?: string
  currency?: string
  price?: number | string
  availableSeats?: number
}

export interface Hotel {
  _id?: string
  name?: string
  city?: string
  location?: { city?: string }
  price?: number | string
  pricePerNight?: number | string
  currency?: string
}

export interface ChatResponse {
  response: string
  flights?: Flight[] | null
  hotels?: Hotel[] | null
}

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  text: string
  flights?: Flight[]
  hotels?: Hotel[]
}
