import { useEffect, useRef } from 'react'

/**
 * Real-physics water ripples that follow the cursor.
 *
 * Physics: discrete 2D wave equation with ping-pong buffers
 *   next[i] = (left + right + top + bottom) / 2 - prev[i]
 *   next[i] *= damping
 *
 * Shading: per-pixel surface-normal lighting (Lambertian diffuse +
 * Phong-style specular) from a virtual sun.
 *
 * Chromatic aberration: each color channel of the specular highlight
 * is sampled at a slightly different position along the surface
 * gradient — red one way, blue the other, green centered. The offset
 * scales with slope steepness, so flat water is colorless and the
 * sharpest crests get the strongest rainbow fringing.
 *
 * The grid renders to a small canvas which the browser scales to the
 * viewport (free bilinear smoothing). Drawn with `screen` blend so
 * highlights lift the UI rather than obscuring it.
 */

const GRID_DIVISOR = 5
const DAMPING = 0.988
const MOVE_THRESHOLD = 4
const MOVE_FORCE = 1.4
const MOVE_RADIUS = 2.8
const CLICK_FORCE = 260
const CLICK_RADIUS = 7

// Direction TO the virtual light (upper-left, mostly overhead). Unit vector.
const LX = 0.35
const LY = -0.35
const LZ = 0.8689

const SHININESS = 24

// Diffuse mint (the body of each ripple)
const BASE_R = 94
const BASE_G = 234
const BASE_B = 212

// Specular near-white tinted toward mint (the crest "shine")
const SPEC_R = 220
const SPEC_G = 255
const SPEC_B = 248

// Chromatic aberration strength. Offset (in grid cells) is proportional
// to gradient magnitude, capped at MAX_CA_OFFSET. Strong gradients =
// stronger refraction = larger color split.
const CA_STRENGTH = 38
const MAX_CA_OFFSET = 4

const ACTIVITY_GAIN = 0.07
const ACTIVITY_CUTOFF = 0.005

export function RippleCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (
      typeof window === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return
    }

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    let gridW = 1
    let gridH = 1
    let bufA = new Float32Array(1)
    let bufB = new Float32Array(1)
    let cur = bufA
    let prev = bufB
    let imageData = ctx.createImageData(1, 1)

    function resize() {
      gridW = Math.max(80, Math.floor(window.innerWidth / GRID_DIVISOR))
      gridH = Math.max(60, Math.floor(window.innerHeight / GRID_DIVISOR))
      canvas!.width = gridW
      canvas!.height = gridH
      bufA = new Float32Array(gridW * gridH)
      bufB = new Float32Array(gridW * gridH)
      cur = bufA
      prev = bufB
      imageData = ctx!.createImageData(gridW, gridH)
    }

    function drop(
      clientX: number,
      clientY: number,
      force: number,
      radius: number,
    ) {
      const gx = (clientX / window.innerWidth) * gridW
      const gy = (clientY / window.innerHeight) * gridH
      const rInt = Math.ceil(radius)
      for (let dy = -rInt; dy <= rInt; dy++) {
        for (let dx = -rInt; dx <= rInt; dx++) {
          const x = Math.floor(gx + dx)
          const y = Math.floor(gy + dy)
          if (x < 1 || x >= gridW - 1 || y < 1 || y >= gridH - 1) continue
          const d = Math.hypot(dx, dy)
          if (d > radius) continue
          const falloff = (1 - d / radius) ** 2
          cur[y * gridW + x] += force * falloff
        }
      }
    }

    let lastX = -1e6
    let lastY = -1e6

    function onMove(e: PointerEvent) {
      const events = (e.getCoalescedEvents?.() ?? [e]) as PointerEvent[]
      for (const ev of events) {
        const dx = ev.clientX - lastX
        const dy = ev.clientY - lastY
        const dist = Math.hypot(dx, dy)
        if (dist < MOVE_THRESHOLD) continue
        lastX = ev.clientX
        lastY = ev.clientY
        const force = Math.min(60, dist * MOVE_FORCE)
        drop(ev.clientX, ev.clientY, force, MOVE_RADIUS)
      }
    }

    function onDown(e: PointerEvent) {
      drop(e.clientX, e.clientY, CLICK_FORCE, CLICK_RADIUS)
    }

    let raf = 0
    function step() {
      // ---- Physics ----
      for (let y = 1; y < gridH - 1; y++) {
        const rowAbove = (y - 1) * gridW
        const row = y * gridW
        const rowBelow = (y + 1) * gridW
        for (let x = 1; x < gridW - 1; x++) {
          const i = row + x
          const sum =
            cur[i - 1] + cur[i + 1] + cur[rowAbove + x] + cur[rowBelow + x]
          let val = sum * 0.5 - prev[i]
          val *= DAMPING
          prev[i] = val
        }
      }
      const tmp = cur
      cur = prev
      prev = tmp

      // ---- Render: surface-shaded + chromatic aberration ----
      const data = imageData.data
      for (let y = 1; y < gridH - 1; y++) {
        const row = y * gridW
        for (let x = 1; x < gridW - 1; x++) {
          const i = row + x
          const h = cur[i]
          const activity = Math.abs(h) * ACTIVITY_GAIN
          const idx = i << 2

          if (activity < ACTIVITY_CUTOFF) {
            data[idx + 3] = 0
            continue
          }

          // ---- Center sample: full lighting ----
          const dhdx = (cur[i + 1] - cur[i - 1]) * 0.5
          const dhdy = (cur[i + gridW] - cur[i - gridW]) * 0.5
          const inv = 1 / Math.sqrt(dhdx * dhdx + dhdy * dhdy + 1)
          const dotL = (-dhdx * LX + -dhdy * LY + LZ) * inv
          const diffuse = dotL > 0 ? dotL : 0
          const specG = Math.pow(diffuse, SHININESS)

          // ---- Chromatic offset ----
          // Refraction direction = gradient direction, magnitude
          // proportional to slope (capped). Red shifts negatively,
          // blue shifts positively — same convention as lens CA.
          const gradMag = Math.sqrt(dhdx * dhdx + dhdy * dhdy)
          let offX = 0
          let offY = 0
          if (gradMag > 0.001) {
            const offsetMag = Math.min(MAX_CA_OFFSET, gradMag * CA_STRENGTH)
            const k = offsetMag / gradMag
            offX = dhdx * k
            offY = dhdy * k
          }

          // ---- Red sample (shifted upstream along gradient) ----
          let specR = 0
          {
            const rx = (x - offX) | 0
            const ry = (y - offY) | 0
            if (rx > 0 && rx < gridW - 1 && ry > 0 && ry < gridH - 1) {
              const ri = ry * gridW + rx
              const ddx = (cur[ri + 1] - cur[ri - 1]) * 0.5
              const ddy = (cur[ri + gridW] - cur[ri - gridW]) * 0.5
              const invR = 1 / Math.sqrt(ddx * ddx + ddy * ddy + 1)
              const dR = (-ddx * LX + -ddy * LY + LZ) * invR
              if (dR > 0) specR = Math.pow(dR, SHININESS)
            }
          }

          // ---- Blue sample (shifted downstream along gradient) ----
          let specB = 0
          {
            const bx = (x + offX) | 0
            const by = (y + offY) | 0
            if (bx > 0 && bx < gridW - 1 && by > 0 && by < gridH - 1) {
              const bi = by * gridW + bx
              const ddx = (cur[bi + 1] - cur[bi - 1]) * 0.5
              const ddy = (cur[bi + gridW] - cur[bi - gridW]) * 0.5
              const invB = 1 / Math.sqrt(ddx * ddx + ddy * ddy + 1)
              const dB = (-ddx * LX + -ddy * LY + LZ) * invB
              if (dB > 0) specB = Math.pow(dB, SHININESS)
            }
          }

          // ---- Compose: mint diffuse body + per-channel specular shine ----
          let r = BASE_R * diffuse + SPEC_R * specR
          let g = BASE_G * diffuse + SPEC_G * specG
          let b = BASE_B * diffuse + SPEC_B * specB
          if (r > 255) r = 255
          if (g > 255) g = 255
          if (b > 255) b = 255

          const meanSpec = (specR + specG + specB) * 0.3333
          const alpha = Math.min(
            220,
            activity * 255 * (0.5 + diffuse * 0.5 + meanSpec * 1.5),
          )

          data[idx] = r
          data[idx + 1] = g
          data[idx + 2] = b
          data[idx + 3] = alpha
        }
      }
      ctx!.putImageData(imageData, 0, 0)

      raf = requestAnimationFrame(step)
    }

    resize()
    raf = requestAnimationFrame(step)
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown, { passive: true })

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-[1] h-full w-full"
      style={{
        mixBlendMode: 'screen',
        opacity: 0.82,
      }}
    />
  )
}
