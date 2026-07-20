import { motion } from "framer-motion";
import { BookOpen, Database, FileCode, PenTool, Download } from "lucide-react";

const docs = [
  { icon: BookOpen, title: "Getting Started", desc: "Set up your environment and begin using EchoBoard for dataset creation." },
  { icon: Database, title: "Dataset Schema", desc: "Understand the ECHD schema — image IDs, metadata fields, and versioning." },
  { icon: FileCode, title: "Metadata Format", desc: "Learn about the JSON metadata structure stored in MongoDB Atlas." },
  { icon: PenTool, title: "Annotation Guide", desc: "Best practices for annotating whiteboard images with text and class labels." },
  { icon: Download, title: "Download Guide", desc: "How to export, version, and download the complete ECHD dataset." },
];

const container = { hidden: {}, show: { transition: { staggerChildren: 0.08 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function DocsSection() {
  return (
    <section id="docs" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-5xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #F59E0B, #EF4444)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Documentation</p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Resources & Guides</h2>
        </motion.div>

        <motion.div variants={container} initial="hidden" whileInView="show" viewport={{ once: true }} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {docs.map(d => (
            <motion.div key={d.title} variants={item} whileHover={{ y: -3 }}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 transition-all duration-300 hover:border-[var(--color-accent-amber)]/30 cursor-pointer group">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3 bg-[var(--color-accent-amber)]/10">
                <d.icon size={18} className="text-[var(--color-accent-amber)]" />
              </div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-1.5 group-hover:text-[var(--color-accent-amber)] transition-colors">{d.title}</h3>
              <p className="text-xs text-[var(--color-text-muted)] leading-relaxed">{d.desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
