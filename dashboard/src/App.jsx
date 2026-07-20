import { useState, useRef, useEffect } from "react";
import { ThemeProvider } from "./ThemeContext";
import Navbar from "./components/Navbar";
import HeroSection from "./components/HeroSection";
import AboutSection from "./components/AboutSection";
import PipelineSection from "./components/PipelineSection";
import ApplicationsSection from "./components/ApplicationsSection";
import StatsBar from "./components/StatsBar";
import UploadPanel from "./components/UploadPanel";
import DatasetExplorer from "./components/DatasetExplorer";
import DocsSection from "./components/DocsSection";
import TeamSection from "./components/TeamSection";
import Footer from "./components/Footer";

const SECTION_IDS = [
  "home", "about", "pipeline", "applications", "statistics",
  "upload", "explorer", "docs", "team", "contact",
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

        <DatasetExplorer refreshKey={refreshKey} />
        <DocsSection />
        <TeamSection />
        <Footer />
      </div>
    </ThemeProvider>
  );
}
