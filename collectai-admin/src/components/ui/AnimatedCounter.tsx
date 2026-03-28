"use client";

import React, { useEffect, useRef, useState } from "react";

interface AnimatedCounterProps {
  value: number;
  duration?: number;
  formatter?: (n: number) => string;
  prefix?: string;
  suffix?: string;
  className?: string;
}

function easeOut(t: number): number {
  return 1 - Math.pow(1 - t, 3);
}

export function AnimatedCounter({
  value,
  duration = 600,
  formatter,
  prefix = "",
  suffix = "",
  className = "",
}: AnimatedCounterProps) {
  const format = formatter ?? ((n: number) => n.toLocaleString());
  const [display, setDisplay] = useState(format(0));
  const prevValueRef = useRef(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const from = prevValueRef.current;
    const to = value;
    const startTime = performance.now();

    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
    }

    function tick(now: number) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOut(progress);
      const current = from + (to - from) * eased;

      setDisplay(format(Math.round(current)));

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setDisplay(format(to));
        prevValueRef.current = to;
      }
    }

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [value, duration, formatter]);

  return (
    <span className={className}>
      {prefix}
      {display}
      {suffix}
    </span>
  );
}
