import { useEffect, useState, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { Image, PenTool, CheckCircle2, Package, Film } from "lucide-react";
import { api } from "../api";

function useAnimatedCounter(target, duration = 1500, inView = true) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!inView || target == null) return;
    const num = typeof target === "number" ? target : parseInt(target) || 0;
    if (num === 0) { setCount(0); return; }
    let start = 0;
    const step = Math.max(1, Math.floor(num / (duration / 16)));
    const timer = setInterval(() => {
      start += step;
      if (start >= num) { setCount(num); clearInterval(timer); }
      else setCount(start);
    }, 16);
    return () => clearInterval(timer);
  }, [target, inView, duration]);
  return count;
}

const statConfig = [
  { key: "total_videos", label: "Videos", icon: Film, color: "var(--color-accent)" },
  { key: "total_images", label: "Dataset Images", icon: Image, color: "var(--color-accent-cyan)" },
  { key: "pending_annotations", label: "Pending", icon: PenTool, color: "var(--color-accent-amber)" },
  { key: "completed_annotations", label: "Annotated", icon: CheckCircle2, color: "var(--color-accent-green)" },
  { key: "current_version", label: "Version", icon: Package, color: "var(--color-accent-purple)", isText: true },
];

const container = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function StatsBar() {
  const [stats, setStats] = useState({
    total_videos: 0,
    total_images: 0,
    pending_annotations: 0,
    completed_annotations: 0,
    current_version: "v1.0.0"
  });
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  useEffect(() => {
    api.getStats().then((res) => {
      if (res) setStats(res);
    }).catch(() => {});
  }, []);

  return (
    <section id="statistics" className="py-28 px-6 sm:px-10 lg:px-16" ref={ref}>
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-14"
        >
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #10B981, #06B6D4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Statistics</p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Dataset at a Glance</h2>
        </motion.div>

        <motion.div variants={container} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-5">
          {statConfig.map(s => (
            <StatCard key={s.key} stat={s} value={stats[s.key]} inView={inView} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function StatCard({ stat, value, inView }) {
  const animated = useAnimatedCounter(stat.isText ? 0 : value, 1200, inView);

  return (
    <motion.div
      variants={item}
      whileHover={{ y: -3 }}
      className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 text-center transition-all duration-300"
    >
      <div className="w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-3" style={{ background: `${stat.color}12` }}>
        <stat.icon size={20} style={{ color: stat.color }} />
      </div>
      <p className="text-2xl font-bold text-[var(--color-text-primary)] mb-1" style={{ fontVariantNumeric: "tabular-nums" }}>
        {stat.isText ? value : animated.toLocaleString()}
      </p>
      <p className="text-xs text-[var(--color-text-muted)] uppercase tracking-wider font-medium">{stat.label}</p>
    </motion.div>
  );
}
