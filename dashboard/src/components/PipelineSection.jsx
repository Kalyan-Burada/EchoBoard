import { motion } from "framer-motion";
import { Upload, FileText, PenTool, ShieldCheck, HardDrive, Database, Search, Tag, ArrowDown } from "lucide-react";

const steps = [
  { icon: Upload, label: "Image Upload", desc: "Capture or upload whiteboard images", color: "#3B82F6" },
  { icon: FileText, label: "Metadata Generation", desc: "Auto-generate ECHD metadata", color: "#6366F1" },
  { icon: PenTool, label: "Annotation", desc: "Label content classes & text", color: "#8B5CF6" },
  { icon: ShieldCheck, label: "Quality Validation", desc: "Ensure dataset consistency", color: "#A855F7" },
  { icon: HardDrive, label: "MinIO Storage", desc: "Store originals in object storage", color: "#06B6D4" },
  { icon: Database, label: "MongoDB Atlas", desc: "Persist structured metadata", color: "#10B981" },
  { icon: Search, label: "Dataset Explorer", desc: "Browse, filter & inspect data", color: "#14B8A6" },
  { icon: Tag, label: "Dataset Release", desc: "Version & publish snapshots", color: "#F59E0B" },
  { icon: ArrowDown, label: "Download Dataset", desc: "Export as structured ZIP", color: "#EF4444" },
];

export default function PipelineSection() {
  return (
    <section id="pipeline" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #06B6D4, #8B5CF6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Pipeline
          </p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">
            End-to-End Data Pipeline
          </h2>
          <p className="text-[var(--color-text-muted)] max-w-lg mx-auto text-base leading-relaxed">
            From raw capture to production-ready dataset in 9 automated stages.
          </p>
        </motion.div>

        <div className="relative">
          {/* Vertical connector line with gradient */}
          <div className="absolute left-6 sm:left-1/2 top-0 bottom-0 w-px sm:-translate-x-px"
            style={{ background: "linear-gradient(180deg, #3B82F6 0%, #8B5CF6 30%, #06B6D4 60%, #10B981 80%, #EF4444 100%)" }} />

          {steps.map((step, i) => (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.4, delay: i * 0.06 }}
              className={`relative flex items-center mb-8 last:mb-0 ${
                i % 2 === 0 ? "sm:flex-row" : "sm:flex-row-reverse"
              }`}
            >
              {/* Content card */}
              <div className={`ml-16 sm:ml-0 sm:w-[calc(50%-36px)] ${i % 2 === 0 ? "sm:pr-4 sm:text-right" : "sm:pl-4 sm:text-left"}`}>
                <motion.div
                  whileHover={{ y: -2 }}
                  className="inline-block rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] px-5 py-4 transition-all duration-300 hover:shadow-lg"
                  style={{ ["--hover-border"]: `${step.color}30` }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = `${step.color}40`; e.currentTarget.style.boxShadow = `0 4px 20px ${step.color}15`; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'var(--color-border)'; e.currentTarget.style.boxShadow = 'none'; }}
                >
                  <p className="text-sm font-semibold text-[var(--color-text-primary)] mb-1">{step.label}</p>
                  <p className="text-xs text-[var(--color-text-muted)]">{step.desc}</p>
                </motion.div>
              </div>

              {/* Center node */}
              <div className="absolute left-0 sm:left-1/2 sm:-translate-x-1/2 z-10">
                <div className="w-12 h-12 rounded-full border-2 bg-[var(--color-bg-primary)] flex items-center justify-center transition-all duration-300"
                  style={{ borderColor: `${step.color}50` }}>
                  <step.icon size={18} style={{ color: step.color }} />
                </div>
              </div>

              {/* Spacer for opposite side */}
              <div className="hidden sm:block sm:w-[calc(50%-36px)]" />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
