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

export interface TraceStep {
  step: number
  node: string
  title: string
  detail: Record<string, unknown>
  duration_ms: number
}

export interface BookingField {
  name: string
  label: string
  type: string // text | email | date | select
  value?: string | null
  options?: string[] | null
}

export interface BookingForm {
  kind: string // "hotel" | "flight"
  title: string
  fields: BookingField[]
}

export interface BookingReviewItem {
  label: string
  value?: string | null
}

export interface BookingReview {
  kind: string // "hotel" | "flight"
  title: string
  items: BookingReviewItem[]
}

export interface ChatResponse {
  response: string
  flights?: Flight[] | null
  hotels?: Hotel[] | null
  trace?: TraceStep[] | null
  booking_form?: BookingForm | null
  booking_review?: BookingReview | null
}

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  text: string
  flights?: Flight[]
  hotels?: Hotel[]
  trace?: TraceStep[]
  bookingForm?: BookingForm
  bookingReview?: BookingReview
}
