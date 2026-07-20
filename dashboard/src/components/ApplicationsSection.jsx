import { motion } from "framer-motion";
import { GraduationCap, ScanText, Calculator, GitBranch, Eye, MonitorPlay, FileStack, FlaskConical } from "lucide-react";

const apps = [
  { icon: GraduationCap, title: "Educational AI", desc: "Train models on real classroom content", color: "#3B82F6", bg: "rgba(59,130,246,0.08)" },
  { icon: ScanText, title: "OCR", desc: "Handwritten text recognition from boards", color: "#06B6D4", bg: "rgba(6,182,212,0.08)" },
  { icon: Calculator, title: "Formula Recognition", desc: "Detect and parse mathematical notation", color: "#8B5CF6", bg: "rgba(139,92,246,0.08)" },
  { icon: GitBranch, title: "Diagram Detection", desc: "Identify diagrams, flowcharts & graphs", color: "#10B981", bg: "rgba(16,185,129,0.08)" },
  { icon: Eye, title: "Vision Language Models", desc: "Multimodal understanding of board content", color: "#F59E0B", bg: "rgba(245,158,11,0.08)" },
  { icon: MonitorPlay, title: "Lecture Understanding", desc: "Temporal analysis of teaching sequences", color: "#F43F5E", bg: "rgba(244,63,94,0.08)" },
  { icon: FileStack, title: "Document AI", desc: "Process handwritten educational documents", color: "#6366F1", bg: "rgba(99,102,241,0.08)" },
  { icon: FlaskConical, title: "AI Research", desc: "Benchmarking and reproducible experiments", color: "#14B8A6", bg: "rgba(20,184,166,0.08)" },
];

const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const item = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function ApplicationsSection() {
  return (
    <section id="applications" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          className="text-center mb-16"
        >
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #8B5CF6, #F43F5E)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Applications
          </p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">
            Powering the Future of Educational AI
          </h2>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5"
        >
          {apps.map((app) => (
            <motion.div
              key={app.title}
              variants={item}
              whileHover={{ y: -6, scale: 1.02 }}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 transition-all duration-300 cursor-default"
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = `${app.color}40`; e.currentTarget.style.boxShadow = `0 8px 30px ${app.color}12`; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.boxShadow = 'none'; }}
            >
              <div className="w-11 h-11 rounded-xl flex items-center justify-center mb-4" style={{ background: app.bg }}>
                <app.icon size={20} style={{ color: app.color }} />
              </div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-2">{app.title}</h3>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">{app.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
