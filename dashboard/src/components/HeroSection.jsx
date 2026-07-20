import { motion } from "framer-motion";
import { ArrowDown, Database, Sparkles } from "lucide-react";
import { api } from "../api";
import { useTheme } from "../ThemeContext";

export default function HeroSection({ onNavigate }) {
  const { dark } = useTheme();

  return (
    <section id="home" className="relative min-h-screen flex items-center justify-center overflow-hidden px-6 sm:px-10 lg:px-16">
      {/* Background effects */}
      <div className="absolute inset-0 grid-bg" />

      {/* Colorful gradient orbs */}
      <div className="absolute top-[15%] left-[10%] w-[500px] h-[500px] bg-[var(--color-accent)]/8 rounded-full blur-[120px] animate-pulse-glow" />
      <div className="absolute bottom-[15%] right-[10%] w-[400px] h-[400px] bg-[var(--color-accent-cyan)]/8 rounded-full blur-[100px] animate-pulse-glow" style={{ animationDelay: "1.5s" }} />
      <div className="absolute top-[40%] right-[30%] w-[300px] h-[300px] bg-[var(--color-accent-purple)]/6 rounded-full blur-[80px] animate-pulse-glow" style={{ animationDelay: "3s" }} />

      <div className="relative z-10 max-w-5xl mx-auto text-center w-full">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          {/* Badge */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.2 }}
            className="flex w-fit mx-auto items-center gap-2 px-5 py-2 rounded-full border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 text-xs font-semibold text-[var(--color-accent)] tracking-wide mb-10"
          >
            <Sparkles size={14} />
            AI-Powered Dataset Generation Platform
          </motion.div>

          {/* Board background behind title */}
          <div className="relative inline-block mb-28 sm:mb-32 mt-12 w-full max-w-[90%] sm:max-w-max mx-auto">
            {/* Board frame */}
            <div
              className="absolute -inset-x-12 -inset-y-6 rounded-2xl border-4"
              style={{
                borderColor: dark ? "#3f3f46" : "#78716c",
                background: dark
                  ? "linear-gradient(145deg, #f5f5f4 0%, #e7e5e4 30%, #d6d3d1 70%, #a8a29e 100%)"
                  : "linear-gradient(145deg, #1c1917 0%, #292524 30%, #1c1917 70%, #0c0a09 100%)",
                boxShadow: dark
                  ? "0 8px 40px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.5)"
                  : "0 8px 40px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1)",
              }}
            >
              {/* Chalk/marker dust marks */}
              <div className="absolute top-3 left-6 w-16 h-[2px] rounded-full opacity-20"
                style={{ background: dark ? "#78716c" : "#a8a29e" }} />
              <div className="absolute bottom-4 right-8 w-12 h-[2px] rounded-full opacity-15"
                style={{ background: dark ? "#78716c" : "#a8a29e" }} />
              <div className="absolute top-5 right-12 w-8 h-[2px] rounded-full opacity-10"
                style={{ background: dark ? "#78716c" : "#a8a29e" }} />
              {/* Board tray */}
              <div
                className="absolute -bottom-3 left-8 right-8 h-3 rounded-b-lg"
                style={{
                  background: dark ? "#57534e" : "#44403c",
                  boxShadow: "0 2px 4px rgba(0,0,0,0.2)"
                }}
              />
            </div>

            {/* Title */}
            <h1 className="relative text-6xl sm:text-7xl lg:text-[6rem] font-black tracking-tight py-2 px-4">
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage: "linear-gradient(135deg, #3B82F6 0%, #06B6D4 50%, #8B5CF6 100%)",
                }}
              >
                Echo
              </span>
              <span
                style={{
                  color: dark ? "#1c1917" : "#fafaf9",
                  textShadow: dark ? "none" : "0 2px 8px rgba(0,0,0,0.3)",
                }}
              >
                Board
              </span>
            </h1>
          </div>

          {/* Tagline */}
          <p className="text-lg sm:text-xl lg:text-2xl font-semibold mb-5 max-w-2xl mx-auto leading-relaxed"
            style={{
              background: "linear-gradient(135deg, var(--color-text-primary) 0%, var(--color-text-secondary) 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Transforming Classroom Knowledge into AI Intelligence.
          </p>

          {/* Problem statement */}
          <p className="text-sm sm:text-base text-[var(--color-text-muted)] max-w-xl mx-auto mb-12 leading-relaxed px-4">
            Modern AI models struggle to understand handwritten classroom whiteboards, equations, and diagrams due to the lack of high-quality annotated datasets. EchoBoard bridges this gap.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-5 px-4">
            <motion.a
              href={api.datasetZipUrl()}
              target="_blank"
              rel="noopener noreferrer"
              whileHover={{ scale: 1.04, y: -2 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-2.5 px-8 py-3.5 rounded-xl text-white font-semibold text-sm shadow-xl no-underline transition-shadow duration-300"
              style={{
                background: "linear-gradient(135deg, #3B82F6 0%, #06B6D4 100%)",
                boxShadow: "0 4px 20px rgba(59, 130, 246, 0.35), 0 0 60px rgba(59, 130, 246, 0.1)",
              }}
            >
              <ArrowDown size={17} />
              Download Dataset
            </motion.a>
            <motion.button
              onClick={() => onNavigate("explorer")}
              whileHover={{ scale: 1.04, y: -2 }}
              whileTap={{ scale: 0.97 }}
              className="inline-flex items-center gap-2.5 px-8 py-3.5 rounded-xl font-semibold text-sm cursor-pointer transition-all duration-300"
              style={{
                border: "1px solid var(--color-border)",
                background: "var(--color-bg-card)",
                color: "var(--color-text-primary)",
                boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
              }}
            >
              <Database size={17} />
              Explore Dataset
            </motion.button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
