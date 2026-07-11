import { useEffect } from 'react'
import type { RefObject } from 'react'
import { liquidGlass } from '../lib/liquid-glass.js'

export interface LiquidGlassOptions {
  scale?: number
  chroma?: number
  border?: number
  mapBlur?: number
  blur?: number
  saturate?: number
  radius?: number | null
  fallbackBlur?: number
}

/**
 * Attach the liquid-glass filter to a ref'd element for its lifetime.
 * Opts are diffed by shallow key set — pass a stable literal to avoid churn.
 */
export function useLiquidGlass(
  ref: RefObject<HTMLElement | null>,
  opts: LiquidGlassOptions = {},
) {
  const key = JSON.stringify(opts)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const glass = liquidGlass(el, opts)
    return () => glass.destroy()
    // opts is captured via `key`; ref is stable
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ref, key])
}
