import { useEffect, useRef } from 'react'

export function useUnsavedGuard(when: boolean, message: string) {
  const messageRef = useRef(message)
  messageRef.current = message

  useEffect(() => {
    if (!when) return

    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
      return ''
    }

    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [when])

  useEffect(() => {
    if (!when) return

    // Prevent accidental browser-back / swipe-back while a dirty modal is open.
    // We push a sentinel entry; on back, we confirm and either allow or restore.
    const state = { __unsaved_guard: true, t: Date.now() }
    try {
      window.history.pushState(state, document.title)
    } catch {
      // ignore
    }

    const onPopState = () => {
      const ok = window.confirm(messageRef.current)
      if (!ok) {
        try {
          window.history.pushState(state, document.title)
        } catch {
          // ignore
        }
      }
    }

    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [when])
}


