import { useState, useRef, useEffect } from "react";
import { ThemeProvider } from "./ThemeContext";
import Navbar from "./components/Navbar";
import HeroSection from "./components/HeroSection";
import AboutSection from "./components/AboutSection";
import PipelineSection from "./components/PipelineSection";
import ApplicationsSection from "./components/ApplicationsSection";
import StatsBar from "./components/StatsBar";
import UploadPanel from "./components/UploadPanel";
import Library from "./components/Library";
import DatasetExplorer from "./components/DatasetExplorer";
import DocsSection from "./components/DocsSection";
import TeamSection from "./components/TeamSection";
import Footer from "./components/Footer";

const SECTION_IDS = [
  "home", "about", "pipeline", "applications", "statistics",
  "upload", "explorer", "datasets", "docs", "team", "contact",
];

export default function App() {
  const [activeSection, setActiveSection] = useState("home");
  const [refreshKey, setRefreshKey] = useState(0);

  function onUploadDone() {
    setRefreshKey(k => k + 1);
  }

  function handleNavigate(id) {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    setActiveSection(id);
  }

  // Track active section on scroll
  useEffect(() => {
    const observer = new IntersectionObserver(
      entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        }
      },
      { rootMargin: "-40% 0px -55% 0px" }
    );

    SECTION_IDS.forEach(id => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-[var(--color-bg-primary)] text-[var(--color-text-primary)]">
        <Navbar activeSection={activeSection} onNavigate={handleNavigate} />

        {/* Landing Page Sections */}
        <HeroSection onNavigate={handleNavigate} />
        <AboutSection />
        <PipelineSection />
        <ApplicationsSection />
        <StatsBar key={`stats-${refreshKey}`} />

        {/* Functional Sections */}
        <UploadPanel onDone={onUploadDone} />

        {/* Library (inline, not a separate section with ID — it's part of the datasets view) */}
        <section id="datasets" className="py-28 px-6 sm:px-10 lg:px-16">
          <div className="max-w-6xl mx-auto">
            <div className="text-center mb-8">
              <p className="text-sm font-bold tracking-widest uppercase mb-4"
                style={{ background: "linear-gradient(135deg, #10B981, #F59E0B)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Dataset Library</p>
              <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Manage Your Datasets</h2>
            </div>
            <Library refreshKey={refreshKey} />
          </div>
        </section>

        <DatasetExplorer refreshKey={refreshKey} />
        <DocsSection />
        <TeamSection />
        <Footer />
      </div>
    </ThemeProvider>
  );
}
