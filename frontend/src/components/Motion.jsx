import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "motion/react";
import { useEffect } from "react";

const ease = [0.22, 1, 0.36, 1];

/** Route-level enter/exit transition. */
export function Page({ children, className = "" }) {
  return (
    <motion.main className={"dashboard-content " + className} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.35, ease }}>
      {children}
    </motion.main>
  );
}

const container = { hidden: {}, show: { transition: { staggerChildren: 0.06 } } };
const item = { hidden: { opacity: 0, y: 14 }, show: { opacity: 1, y: 0, transition: { duration: 0.45, ease } } };

/** Children marked with <Rise> animate in one after another. */
export function Stagger({ children, className = "", as = "div" }) {
  const Tag = motion[as];
  return <Tag className={className} variants={container} initial="hidden" animate="show">{children}</Tag>;
}

export function Rise({ children, className = "", as = "div", ...rest }) {
  const Tag = motion[as];
  return <Tag className={className} variants={item} {...rest}>{children}</Tag>;
}

/** Counts up to `value` (a real number from the API); renders "—" when absent. */
export function AnimatedNumber({ value, digits = 1 }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(value ?? 0);
  const text = useTransform(mv, (v) => v.toFixed(digits));
  useEffect(() => {
    if (value === null || value === undefined) return;
    if (reduce) return void mv.set(value);
    const controls = animate(mv, value, { duration: 0.8, ease });
    return () => controls.stop();
  }, [value, reduce, mv]);
  if (value === null || value === undefined) return <>—</>;
  return <motion.span>{text}</motion.span>;
}

/** Animated horizontal bar (weights, skill). */
export function Bar({ value, max = 1, color, className = "" }) {
  const width = Math.max(0, Math.min(1, (value ?? 0) / (max || 1))) * 100;
  return (
    <div className={"bar " + className}>
      <motion.span style={{ background: color }} initial={{ width: 0 }} animate={{ width: width + "%" }} transition={{ duration: 0.7, ease }} />
    </div>
  );
}

/** Loading placeholder: shows shape, never numbers. */
export function Skeleton({ height = 16, width = "100%", className = "" }) {
  return <span className={"skeleton " + className} style={{ height, width }} aria-hidden="true" />;
}

export function SkeletonCard({ lines = 4, height = 180 }) {
  return (
    <div className="dashboard-card skeleton-card" aria-busy="true" aria-label="Loading">
      <Skeleton width="40%" height={14} />
      <div style={{ height: 10 }} />
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} width={`${90 - i * 12}%`} height={10} className="skeleton--line" />)}
      <Skeleton height={height} className="skeleton--block" />
    </div>
  );
}
