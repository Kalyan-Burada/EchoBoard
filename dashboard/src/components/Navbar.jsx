import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Sun, Moon, Menu, X } from "lucide-react";
import { useTheme } from "../ThemeContext";

const NAV_ITEMS = [
  { label: "Home", id: "home" },
  { label: "About", id: "about" },
  { label: "Pipeline", id: "pipeline" },
  { label: "Applications", id: "applications" },
  { label: "Statistics", id: "statistics" },
  { label: "Upload", id: "upload" },
  { label: "Explorer", id: "explorer" },
  { label: "Datasets", id: "datasets" },
  { label: "Docs", id: "docs" },
  { label: "Team", id: "team" },
];

export default function Navbar({ activeSection, onNavigate }) {
  const { dark, toggle } = useTheme();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  function handleNav(id) {
    onNavigate(id);
    setMobileOpen(false);
  }

  return (
    <motion.nav
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5 }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? "glass shadow-lg shadow-black/5"
          : "bg-transparent"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <button onClick={() => handleNav("home")} className="flex items-center gap-2.5 group cursor-pointer bg-transparent border-none">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-cyan)] flex items-center justify-center">
              <span className="text-white text-sm font-bold">E</span>
            </div>
            <span className="text-lg font-bold text-[var(--color-text-primary)] group-hover:opacity-80 transition-opacity">
              EchoBoard
            </span>
            <span className="hidden sm:inline-block text-[10px] font-semibold tracking-wider px-1.5 py-0.5 rounded bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent-cyan)] text-white">
              ECHD
            </span>
          </button>

          {/* Desktop Nav */}
          <div className="hidden lg:flex items-center gap-1">
            {NAV_ITEMS.map(item => (
              <button
                key={item.id}
                onClick={() => handleNav(item.id)}
                className={`relative px-3 py-1.5 text-[13px] font-medium rounded-lg transition-all duration-200 cursor-pointer bg-transparent border-none ${
                  activeSection === item.id
                    ? "text-[var(--color-accent)]"
                    : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-card)]"
                }`}
              >
                {item.label}
                {activeSection === item.id && (
                  <motion.div
                    layoutId="activeNav"
                    className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 h-0.5 bg-[var(--color-accent)] rounded-full"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </button>
            ))}
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              className="p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-card)] transition-all duration-200 cursor-pointer bg-transparent border-none"
              aria-label="Toggle theme"
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="lg:hidden p-2 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-card)] transition-all cursor-pointer bg-transparent border-none"
            >
              {mobileOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="lg:hidden glass border-t border-[var(--color-border)] px-4 py-3"
        >
          {NAV_ITEMS.map(item => (
            <button
              key={item.id}
              onClick={() => handleNav(item.id)}
              className={`block w-full text-left px-3 py-2.5 text-sm rounded-lg transition-all cursor-pointer bg-transparent border-none ${
                activeSection === item.id
                  ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)]"
              }`}
            >
              {item.label}
            </button>
          ))}
        </motion.div>
      )}
    </motion.nav>
  );
}
