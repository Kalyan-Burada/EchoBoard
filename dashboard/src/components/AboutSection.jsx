import { motion } from "framer-motion";
import { BookOpen, Target, Lightbulb, Layers } from "lucide-react";

const cards = [
  {
    icon: BookOpen,
    title: "About EchoBoard",
    desc: "An AI-powered platform for collecting, managing, annotating, and distributing whiteboard image datasets. Built for the research community to advance educational AI.",
    color: "#3B82F6",
    glow: "rgba(59, 130, 246, 0.08)",
  },
  {
    icon: Lightbulb,
    title: "Why It Was Created",
    desc: "Existing datasets focus on printed text and natural images. There is a critical gap in high-quality, annotated classroom whiteboard data needed for training robust AI models.",
    color: "#06B6D4",
    glow: "rgba(6, 182, 212, 0.08)",
  },
  {
    icon: Target,
    title: "Research Motivation",
    desc: "Enable breakthroughs in OCR for handwriting, mathematical formula recognition, diagram detection, and vision-language models tailored to educational content.",
    color: "#8B5CF6",
    glow: "rgba(139, 92, 246, 0.08)",
  },
  {
    icon: Layers,
    title: "Project Objective",
    desc: "Build a comprehensive, versioned, and annotated dataset (ECHD) with standardized metadata — stored on MinIO and MongoDB Atlas — accessible for reproducible AI research.",
    color: "#10B981",
    glow: "rgba(16, 185, 129, 0.08)",
  },
];

const container = { hidden: {}, show: { transition: { staggerChildren: 0.12 } } };
const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export default function AboutSection() {
  return (
    <section id="about" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #3B82F6, #06B6D4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            About
          </p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">
            Bridging the Data Gap in Educational AI
          </h2>
          <p className="text-[var(--color-text-muted)] max-w-xl mx-auto text-base leading-relaxed">
            EchoBoard is a research-grade dataset platform purpose-built for the classroom domain.
          </p>
        </motion.div>

        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-100px" }}
          className="grid grid-cols-1 md:grid-cols-2 gap-6"
        >
          {cards.map((card) => (
            <motion.div
              key={card.title}
              variants={item}
              whileHover={{ y: -4, scale: 1.01 }}
              className="group relative rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-7 sm:p-8 transition-all duration-300"
              style={{
                boxShadow: `0 0 0 transparent`,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.boxShadow = `0 4px 30px ${card.glow}`; e.currentTarget.style.borderColor = `${card.color}30`; }}
              onMouseLeave={(e) => { e.currentTarget.style.boxShadow = `0 0 0 transparent`; e.currentTarget.style.borderColor = `var(--color-border)`; }}
            >
              {/* Colored accent bar */}
              <div className="absolute top-0 left-8 right-8 h-[2px] rounded-b-full opacity-60" style={{ background: `linear-gradient(90deg, transparent, ${card.color}, transparent)` }} />
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
                style={{ background: `${card.color}15` }}
              >
                <card.icon size={22} style={{ color: card.color }} />
              </div>
              <h3 className="text-lg font-semibold text-[var(--color-text-primary)] mb-3">{card.title}</h3>
              <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">{card.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
