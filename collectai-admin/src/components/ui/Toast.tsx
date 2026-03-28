"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

type ToastType = "info" | "success" | "warning" | "error";

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

type ToastInput = Omit<Toast, "id">;

interface ToastContextValue {
  toast: (opts: ToastInput) => void;
  dismiss: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let counter = 0;
function genId() {
  return `toast-${++counter}-${Date.now()}`;
}

const typeStyles: Record<ToastType, string> = {
  info: "border-blue-400 bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-200",
  success:
    "border-green-400 bg-green-50 dark:bg-green-900/30 text-green-800 dark:text-green-200",
  warning:
    "border-amber-400 bg-amber-50 dark:bg-amber-900/30 text-amber-800 dark:text-amber-200",
  error:
    "border-red-400 bg-red-50 dark:bg-red-900/30 text-red-800 dark:text-red-200",
};

const iconMap: Record<ToastType, string> = {
  info: "i",
  success: "\u2713",
  warning: "!",
  error: "\u2715",
};

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (id: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(null);

  useEffect(() => {
    // Trigger slide-in on next frame
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  useEffect(() => {
    const dur = toast.duration ?? 5000;
    timerRef.current = setTimeout(() => {
      setVisible(false);
      setTimeout(() => onDismiss(toast.id), 300);
    }, dur);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className={`
        flex items-start gap-3 w-80 border-l-4 rounded-lg shadow-lg p-4
        transition-all duration-300 ease-out
        ${visible ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"}
        ${typeStyles[toast.type]}
      `}
    >
      <span className="flex-shrink-0 mt-0.5 font-bold text-sm">
        {iconMap[toast.type]}
      </span>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-sm">{toast.title}</p>
        {toast.message && (
          <p className="text-xs mt-0.5 opacity-80">{toast.message}</p>
        )}
      </div>
      <button
        onClick={() => {
          setVisible(false);
          setTimeout(() => onDismiss(toast.id), 300);
        }}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity text-sm leading-none"
        aria-label="Close"
      >
        &times;
      </button>
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback((opts: ToastInput) => {
    const id = genId();
    setToasts((prev) => [...prev, { ...opts, id }]);
  }, []);

  return (
    <ToastContext.Provider value={{ toast: addToast, dismiss }}>
      {children}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
