import { useEffect, useCallback, useRef, useState } from "react"

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  enabled = true,
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const cancelRef = useRef(false)
  const fetchRef = useRef(0)
  // Keep the fetcher in a ref so `start` stays stable across renders. An inline
  // arrow fetcher (e.g. `() => api.config()`) would otherwise change identity on
  // every render, restarting the polling effect and racing `refresh()` results.
  const fetcherRef = useRef(fetcher)
  useEffect(() => {
    fetcherRef.current = fetcher
  }, [fetcher])

  const start = useCallback(async (id: number) => {
    try {
      const result = await fetcherRef.current()
      if (cancelRef.current || id !== fetchRef.current) return
      setData(result)
      setError(null)
    } catch (err: unknown) {
      if (cancelRef.current || id !== fetchRef.current) return
      setError(err instanceof Error ? err.message : "请求失败")
    } finally {
      if (!cancelRef.current && id === fetchRef.current) {
        setLoading(false)
      }
    }
  }, [])

  const refresh = useCallback(() => {
    const id = ++fetchRef.current
    setLoading(true)
    void start(id)
  }, [start])

  useEffect(() => {
    if (!enabled) return

    const id = ++fetchRef.current
    cancelRef.current = false

    const poll = async () => {
      await start(id)
      if (!cancelRef.current && intervalMs > 0) {
        await new Promise((r) => setTimeout(r, intervalMs))
        if (!cancelRef.current) poll()
      }
    }

    void poll()

    return () => {
      cancelRef.current = true
    }
  }, [intervalMs, enabled, start])

  return { data, loading, error, refresh }
}
