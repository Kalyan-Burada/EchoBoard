import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowDown, Database, Sparkles } from "lucide-react";
import { api } from "../api";
import { useTheme } from "../ThemeContext";

export default function HeroSection({ onNavigate }) {
  const { dark } = useTheme();
  const [phase, setPhase] = useState("greeting"); // "greeting" -> "erasing" -> "echoboard"

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("erasing"), 2000);
    const t2 = setTimeout(() => setPhase("echoboard"), 3500);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  return (
    <section id="home" className="relative min-h-screen flex flex-col justify-center overflow-hidden px-6 sm:px-10 lg:px-16 pt-24 pb-12">
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
              className="absolute -inset-x-4 sm:-inset-x-12 -inset-y-4 sm:-inset-y-6 rounded-2xl border-4"
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
            <h1 className="relative text-5xl sm:text-7xl lg:text-[6rem] font-black tracking-tight py-2 px-4 flex items-center justify-center">
              
              {/* Invisible placeholder to maintain layout size */}
              <div className="invisible opacity-0 pointer-events-none" aria-hidden="true">
                <span>Echo</span><span>Board</span>
              </div>

              {/* Greeting Text */}
              <AnimatePresence>
                {(phase === "greeting" || phase === "erasing") && (
                  <motion.div
                    className="absolute inset-0 flex items-center justify-center whitespace-nowrap"
                    initial={{ clipPath: "inset(0 0% 0 0)" }}
                    animate={phase === "erasing" ? { 
                      clipPath: [
                        "inset(0 0% 0 0)", 
                        "inset(0 15% 0 0)", 
                        "inset(0 10% 0 0)", 
                        "inset(0 30% 0 0)", 
                        "inset(0 25% 0 0)", 
                        "inset(0 50% 0 0)", 
                        "inset(0 45% 0 0)", 
                        "inset(0 70% 0 0)", 
                        "inset(0 65% 0 0)", 
                        "inset(0 90% 0 0)", 
                        "inset(0 85% 0 0)", 
                        "inset(0 100% 0 0)"
                      ] 
                    } : {}}
                    transition={{ duration: 1.5, ease: "easeInOut" }}
                    exit={{ opacity: 0 }}
                  >
                    <span 
                      className="drop-shadow-md" 
                      style={{ color: dark ? "#1c1917" : "#ffffff", fontFamily: "'Comic Sans MS', 'Chalkboard SE', cursive" }}
                    >
                      Hi Learners!
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* EchoBoard Text */}
              <AnimatePresence>
                {phase === "echoboard" && (
                  <motion.div
                    className="absolute inset-0 flex items-center justify-center whitespace-nowrap"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                  >
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
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Duster */}
              <AnimatePresence>
                {phase === "erasing" && (
                  <motion.div
                    className="absolute top-0 bottom-0 z-20 flex items-center"
                    initial={{ left: "100%", x: "0%", y: "0%", rotate: 0 }}
                    animate={{ 
                      left: ["100%", "85%", "90%", "70%", "75%", "50%", "55%", "30%", "35%", "10%", "15%", "-10%"],
                      y: ["0%", "20%", "-20%", "30%", "-30%", "35%", "-35%", "25%", "-25%", "15%", "-15%", "0%"],
                      rotate: [0, 10, -10, 15, -15, 20, -20, 15, -15, 10, -10, 0],
                      x: "-100%" 
                    }}
                    transition={{ duration: 1.5, ease: "easeInOut" }}
                  >
                    <div className="w-16 sm:w-20 h-20 sm:h-28 rounded-md shadow-[0_10px_20px_rgba(0,0,0,0.5)] flex flex-col overflow-hidden" 
                         style={{ background: "#8B5A2B" }}> {/* Wood back */}
                      {/* Wood texture lines */}
                      <div className="flex-1 opacity-20" 
                           style={{ backgroundImage: "repeating-linear-gradient(90deg, transparent, transparent 4px, rgba(0,0,0,0.2) 4px, rgba(0,0,0,0.2) 8px)" }} />
                      {/* White felt erasing pad */}
                      <div className="h-5 sm:h-7 bg-[#e5e7eb] border-t-2 border-[#d1d5db] shadow-inner" />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
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
