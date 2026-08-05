import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, RefreshCw, Trash2, X, Plus, Package, Sparkles, CheckCircle2 } from "lucide-react";
import { api } from "../api";

const CLASSES = ["Text", "Equation", "Heading", "Diagram", "Table", "Other"];

export default function DatasetExplorer({ refreshKey }) {
  const [images, setImages] = useState([]);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);
  const [filterSubject, setFilterSubject] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterVersion, setFilterVersion] = useState("");
  const [filterWriter, setFilterWriter] = useState("");
  const [newVersionDesc, setNewVersionDesc] = useState("");
  const [versionMsg, setVersionMsg] = useState(null);
  const [visibleCount, setVisibleCount] = useState(12);

  // OCR & Annotation Verification states
  const [ocrLoading, setOcrLoading] = useState(false);
  const [annText, setAnnText] = useState("");
  const [annClass, setAnnClass] = useState("Text");
  const [annMsg, setAnnMsg] = useState(null);

  function loadImages() {
    setLoading(true);
    setVisibleCount(12);
    const params = {};
    if (filterSubject) params.subject = filterSubject;
    if (filterStatus) params.annotation_status = filterStatus;
    if (filterVersion) params.dataset_version = filterVersion;
    if (filterWriter) params.writer_id = filterWriter;
    api.getDatasetImages(params).then(imgs => { setImages(imgs); setLoading(false); }).catch(() => setLoading(false));
  }

  function loadVersions() { api.getVersions().then(setVersions).catch(() => {}); }

  useEffect(() => { loadImages(); loadVersions(); }, [refreshKey, filterSubject, filterStatus, filterVersion, filterWriter]);

  useEffect(() => {
    if (selectedImage) {
      const existingText = selectedImage.annotations?.[0]?.text || "";
      const existingClass = selectedImage.annotations?.[0]?.class || "Text";
      setAnnText(existingText);
      setAnnClass(existingClass);
      setAnnMsg(null);
    }
  }, [selectedImage]);

  async function handleRunOcr() {
    if (!selectedImage) return;
    setOcrLoading(true);
    setAnnMsg(null);
    try {
      const res = await api.runOcr(selectedImage.id || selectedImage.image_id);
      setAnnText(res.ocr_text || "");
      setAnnMsg("✨ OCR extracted text! Please verify below.");
      loadImages();
    } catch {
      setAnnMsg("❌ OCR extraction failed.");
    }
    setOcrLoading(false);
  }

  async function handleSaveAnnotation() {
    if (!selectedImage) return;
    try {
      await api.updateAnnotation(selectedImage.id || selectedImage.image_id, annText, annClass, true);
      setAnnMsg("✅ Annotation verified & saved!");
      loadImages();
      setTimeout(() => setAnnMsg(null), 3000);
    } catch {
      setAnnMsg("❌ Failed to save annotation.");
    }
  }

  async function handleCreateVersion() {
    try {
      const res = await api.createVersion(newVersionDesc);
      setVersionMsg(`Created ${res.version}`);
      setNewVersionDesc("");
      loadVersions();
      setTimeout(() => setVersionMsg(null), 3000);
    } catch { setVersionMsg("Failed to create version"); }
  }

  async function handleDeleteImage(imageId) {
    await api.deleteDatasetImage(imageId);
    setImages(prev => prev.filter(i => i.image_id !== imageId));
    if (selectedImage?.image_id === imageId) setSelectedImage(null);
  }

  const subjects = [...new Set(images.map(i => i.subject))];
  const writers = [...new Set(images.map(i => i.writer_id))];

  const selectClass = "px-3 py-2 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs focus:border-[var(--color-accent)] focus:outline-none transition-colors appearance-none cursor-pointer";

  return (
    <section id="explorer" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-7xl mx-auto">
        <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-center mb-12">
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #06B6D4, #3B82F6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Explorer</p>
          <h2 className="text-3xl sm:text-4xl font-extrabold text-[var(--color-text-primary)] tracking-tight">Dataset Explorer</h2>
          <p className="mt-4 text-[var(--color-text-secondary)] text-sm max-w-xl mx-auto">Filter, annotate with OCR, verify, and version the EchoBoard Handwritten Dataset.</p>
        </motion.div>

        {/* Filters */}
        <div className="p-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)] font-semibold flex items-center gap-1"><Search size={13} /> Filter:</span>
            <select value={filterSubject} onChange={e => setFilterSubject(e.target.value)} className={selectClass}>
              <option value="">All Subjects</option>
              {subjects.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className={selectClass}>
              <option value="">All Status</option>
              <option value="Pending">⏳ Pending</option>
              <option value="Completed">✅ Completed</option>
            </select>
            <select value={filterVersion} onChange={e => setFilterVersion(e.target.value)} className={selectClass}>
              <option value="">All Versions</option>
              {versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <select value={filterWriter} onChange={e => setFilterWriter(e.target.value)} className={selectClass}>
              <option value="">All Writers</option>
              {writers.map(w => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
          <button onClick={loadImages} className="p-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] text-[var(--color-text-secondary)] hover:text-[var(--color-accent)] cursor-pointer transition-colors">
            <RefreshCw size={14} />
          </button>
        </div>

        {/* Main Section */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Image Grid */}
          <div className="flex-1">
            <p className="text-xs text-[var(--color-text-muted)] mb-4">{loading ? "Loading images..." : `${images.length} dataset images`}</p>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {images.slice(0, visibleCount).map(img => (
                <motion.div
                  key={img.image_id}
                  onClick={() => setSelectedImage(img)}
                  whileHover={{ scale: 1.02 }}
                  className={`rounded-xl border bg-[var(--color-bg-card)] overflow-hidden cursor-pointer transition-colors ${selectedImage?.image_id === img.image_id ? "border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]" : "border-[var(--color-border)]"}`}
                >
                  <img src={api.imageUrl(img.id)} alt={img.image_id} className="w-full aspect-[4/3] object-cover bg-[var(--color-bg-primary)]" />
                  <div className="p-2.5">
                    <span className="text-[11px] font-mono font-bold text-[var(--color-accent-cyan)] block truncate">{img.image_id}</span>
                    <span className={`inline-block text-[9px] font-semibold rounded px-1.5 py-0.5 mt-1 ${img.annotation_status === "Pending" ? "bg-[var(--color-accent-amber)]/10 text-[var(--color-accent-amber)]" : "bg-[var(--color-accent-green)]/10 text-[var(--color-accent-green)]"}`}>
                      {img.annotation_status === "Pending" ? "⏳ Pending" : "✅ Completed"}
                    </span>
                  </div>
                </motion.div>
              ))}
            </div>
            {visibleCount < images.length && (
              <div className="mt-8 text-center">
                <button
                  onClick={() => setVisibleCount(prev => prev + 12)}
                  className="px-6 py-2.5 rounded-xl text-sm font-semibold border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-primary)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-all cursor-pointer"
                >
                  Load More ({images.length - visibleCount} remaining)
                </button>
              </div>
            )}
          </div>

          {/* Detail & Annotation Verification Panel */}
          <AnimatePresence>
            {selectedImage && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="lg:w-80 shrink-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 max-h-[85vh] overflow-auto space-y-4"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold font-mono text-[var(--color-accent-cyan)]">{selectedImage.image_id}</h4>
                  <button onClick={() => setSelectedImage(null)} className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer bg-transparent border-none">
                    <X size={16} />
                  </button>
                </div>
                <img src={api.imageUrl(selectedImage.id)} alt={selectedImage.image_id} className="w-full rounded-lg border border-[var(--color-border)]" />

                {/* OCR & Human Verification Box */}
                <div className="p-3.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-primary)] space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-[var(--color-text-primary)] flex items-center gap-1.5">
                      <Sparkles size={14} className="text-[var(--color-accent-cyan)]" /> OCR Annotation
                    </span>
                    <button
                      onClick={handleRunOcr}
                      disabled={ocrLoading}
                      className="px-2.5 py-1 rounded-lg text-[10px] font-semibold bg-[var(--color-accent)]/15 text-[var(--color-accent)] border border-[var(--color-accent)]/30 hover:bg-[var(--color-accent)]/25 cursor-pointer disabled:opacity-50 transition-colors"
                    >
                      {ocrLoading ? "Running OCR..." : "✨ Auto OCR"}
                    </button>
                  </div>

                  {/* Editable Annotation Text */}
                  <div className="space-y-1">
                    <label className="text-[10px] text-[var(--color-text-muted)] font-medium">Verify / Edit Text:</label>
                    <textarea
                      value={annText}
                      onChange={e => setAnnText(e.target.value)}
                      placeholder="Extracted OCR whiteboard text..."
                      rows={3}
                      className="w-full p-2.5 rounded-lg bg-[var(--color-bg-card)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] focus:border-[var(--color-accent)] focus:outline-none transition-colors resize-none font-mono"
                    />
                  </div>

                  {/* Class Selection & Save */}
                  <div className="flex items-center gap-2">
                    <select
                      value={annClass}
                      onChange={e => setAnnClass(e.target.value)}
                      className="flex-1 px-2 py-1.5 rounded-lg bg-[var(--color-bg-card)] border border-[var(--color-border)] text-xs text-[var(--color-text-primary)] focus:outline-none cursor-pointer"
                    >
                      {CLASSES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                    <button
                      onClick={handleSaveAnnotation}
                      className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--color-accent-green)] text-white border-none cursor-pointer hover:opacity-90 transition-opacity flex items-center gap-1"
                    >
                      <CheckCircle2 size={12} /> Verify
                    </button>
                  </div>

                  {annMsg && <p className="text-[11px] font-medium text-[var(--color-accent-cyan)]">{annMsg}</p>}
                </div>

                {/* Metadata Summary */}
                <div className="space-y-1">
                  {[
                    { l: "Image ID", v: selectedImage.image_id, mono: true },
                    { l: "Subject", v: selectedImage.subject },
                    { l: "Board Type", v: selectedImage.board_type },
                    { l: "Writer", v: selectedImage.writer_id },
                    { l: "Status", v: selectedImage.annotation_status, color: selectedImage.annotation_status === "Pending" ? "var(--color-accent-amber)" : "var(--color-accent-green)" },
                    { l: "Version", v: selectedImage.dataset_version },
                    { l: "Storage Path", v: selectedImage.image_path, mono: true },
                  ].map(m => (
                    <div key={m.l} className="flex justify-between py-1 border-b border-[var(--color-border)]/40">
                      <span className="text-[10px] text-[var(--color-text-muted)]">{m.l}</span>
                      <span className={`text-[10px] max-w-[55%] truncate text-right ${m.mono ? "font-mono" : ""}`} style={{ color: m.color || "var(--color-text-secondary)" }}>{m.v}</span>
                    </div>
                  ))}
                </div>

                <button onClick={() => handleDeleteImage(selectedImage.image_id)} className="w-full py-2 rounded-lg text-xs font-semibold border border-[var(--color-accent-rose)]/20 bg-[var(--color-accent-rose)]/8 text-[var(--color-accent-rose)] hover:bg-[var(--color-accent-rose)]/15 cursor-pointer transition-colors flex items-center justify-center gap-1.5">
                  <Trash2 size={13} /> Delete Image
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Version Management */}
        <div className="mt-8 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5">
          <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-4 flex items-center gap-2">
            <Package size={14} /> Dataset Versions
          </h4>
          <div className="flex gap-3 flex-wrap mb-4">
            {versions.map(v => (
              <div key={v.version} className="px-4 py-2.5 rounded-xl bg-[var(--color-accent-purple)]/8 border border-[var(--color-accent-purple)]/15">
                <p className="text-sm font-bold text-[var(--color-accent-purple)]">{v.version}</p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">{v.image_count} images · {v.created_at?.slice(0, 10)}</p>
                {v.description && <p className="text-[10px] text-[var(--color-text-secondary)] italic mt-0.5">{v.description}</p>}
              </div>
            ))}
            {versions.length === 0 && <p className="text-xs text-[var(--color-text-muted)]">No versions created yet. Images default to ECHD_v1.</p>}
          </div>
          <div className="flex gap-2">
            <input value={newVersionDesc} onChange={e => setNewVersionDesc(e.target.value)}
              placeholder="Version description (optional)"
              className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs focus:border-[var(--color-accent)] focus:outline-none transition-colors" />
            <button onClick={handleCreateVersion} className="px-4 py-2 rounded-lg text-xs font-semibold bg-gradient-to-r from-[var(--color-accent-purple)] to-[#7c3aed] text-white border-none cursor-pointer flex items-center gap-1.5">
              <Plus size={13} /> Create Version
            </button>
          </div>
          {versionMsg && <p className="text-xs text-[var(--color-accent-green)] mt-2">{versionMsg}</p>}
        </div>
      </div>
    </section>
  );
}
