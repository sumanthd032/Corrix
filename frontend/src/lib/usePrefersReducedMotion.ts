import { useEffect, useState } from 'react'

/** Shared across every Framer Motion and React Three Fiber moment in the
 * app so a single source of truth decides when to fall back to a static
 * or near-static presentation, rather than each component re-querying
 * the media query independently. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches)
    query.addEventListener('change', handler)
    return () => query.removeEventListener('change', handler)
  }, [])

  return reduced
}
