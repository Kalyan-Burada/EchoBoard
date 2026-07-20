import { ExternalLink, Mail, BookOpen } from "lucide-react";

export default function Footer() {
  return (
    <footer id="contact" className="border-t border-[var(--color-border)] py-10 px-6">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-[var(--color-accent)] to-[var(--color-accent-cyan)] flex items-center justify-center">
            <span className="text-white text-[10px] font-bold">E</span>
          </div>
          <span className="text-sm font-semibold text-[var(--color-text-primary)]">EchoBoard</span>
          <span className="text-xs text-[var(--color-text-muted)]">· ECHD Dataset Platform</span>
        </div>

        <div className="flex items-center gap-4">
          <a href="mailto:echoboard@research.ai" className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors no-underline">
            <Mail size={13} /> Contact
          </a>
          <a href="https://github.com/Shanmukha-Gautam-Pidaparthi/EchoBoard" target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors no-underline">
            <ExternalLink size={13} /> GitHub
          </a>
          <a href="#docs" className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] transition-colors no-underline">
            <BookOpen size={13} /> Docs
          </a>
        </div>

        <p className="text-[11px] text-[var(--color-text-muted)]">
          © {new Date().getFullYear()} EchoBoard. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
