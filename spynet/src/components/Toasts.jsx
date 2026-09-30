import React, { useCallback, useRef, useState } from 'react';

export function useToasts() {
  const [toasts, setToasts] = useState([]);
  const idRef = useRef(0);
  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const toast = useCallback((message, kind = 'info') => {
    const id = ++idRef.current;
    setToasts((t) => [...t, { id, message, kind }]);
    setTimeout(() => dismiss(id), kind === 'error' ? 7000 : 3500);
  }, [dismiss]);
  return { toasts, toast, dismiss };
}

export default function Toasts({ toasts, dismiss }) {
  if (!toasts.length) return null;
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <button key={t.id} className={`toast ${t.kind}`} onClick={() => dismiss(t.id)}>{t.message}</button>
      ))}
    </div>
  );
}
