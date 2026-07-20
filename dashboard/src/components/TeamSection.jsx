import { motion } from "framer-motion";
import { ExternalLink, Link } from "lucide-react";

const team = [
  {
    name: "Shanmukha Gautam",
    role: "Project Lead & ML Engineer",
    github: "https://github.com/Shanmukha-Gautam-Pidaparthi",
    linkedin: "#",
    initials: "SG",
  },
  {
    name: "Kalyan Burada",
    role: "Project Lead & ML Engineer",
    github: "https://github.com/Kalyan-Burada",
    linkedin: "https://www.linkedin.com/in/burada-kalyan-b65a58292/",
    initials: "KB",
  },
];

const container = { hidden: {}, show: { transition: { staggerChildren: 0.1 } } };
const item = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0, transition: { duration: 0.4 } } };

export default function TeamSection() {
  return (
    <section id="team" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-4xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-14">
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #8B5CF6, #3B82F6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Team</p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Built by Researchers</h2>
        </motion.div>

        <motion.div variants={container} initial="hidden" whileInView="show" viewport={{ once: true }}
          className="flex justify-center gap-5 flex-wrap">
          {team.map(m => (
            <motion.div key={m.name} variants={item} whileHover={{ y: -4 }}
              className="w-60 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 text-center transition-all duration-300 hover:border-[var(--color-accent-purple)]/30">
              {/* Avatar */}
              <div className="w-20 h-20 rounded-full mx-auto mb-4 bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-cyan)] flex items-center justify-center">
                <span className="text-xl font-bold text-white">{m.initials}</span>
              </div>
              <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-0.5">{m.name}</h3>
              <p className="text-xs text-[var(--color-text-muted)] mb-4">{m.role}</p>
              <div className="flex justify-center gap-2">
                <a href={m.github} target="_blank" rel="noopener noreferrer"
                  className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-border)]/80 transition-all">
                  <ExternalLink size={15} />
                </a>
                <a href={m.linkedin} target="_blank" rel="noopener noreferrer"
                  className="p-2 rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:border-[var(--color-border)]/80 transition-all">
                  <Link size={15} />
                </a>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
