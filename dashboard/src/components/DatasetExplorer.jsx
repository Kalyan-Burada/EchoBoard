import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Search, RefreshCw, Trash2, X, Plus, Package } from "lucide-react";
import { api } from "../api";

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
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Dataset Explorer</h2>
        </motion.div>

        {/* Filters */}
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-4 mb-6">
          <div className="flex items-center gap-2 flex-wrap">
            <Search size={14} className="text-[var(--color-text-muted)]" />
            <select value={filterSubject} onChange={e => setFilterSubject(e.target.value)} className={selectClass}>
              <option value="">All Subjects</option>
              {subjects.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} className={selectClass}>
              <option value="">All Status</option>
              <option value="Pending">Pending</option>
              <option value="Completed">Completed</option>
            </select>
            <select value={filterVersion} onChange={e => setFilterVersion(e.target.value)} className={selectClass}>
              <option value="">All Versions</option>
              {versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
            </select>
            <select value={filterWriter} onChange={e => setFilterWriter(e.target.value)} className={selectClass}>
              <option value="">All Writers</option>
              {writers.map(w => <option key={w} value={w}>{w}</option>)}
            </select>
            <button onClick={loadImages} className="p-2 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-primary)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer transition-colors">
              <RefreshCw size={14} />
            </button>
          </div>
        </div>

        {/* Main Layout */}
        <div className="flex gap-5 flex-col lg:flex-row">
          {/* Grid */}
          <div className="flex-1 min-w-0">
            <p className="text-xs text-[var(--color-text-muted)] mb-3">
              {loading ? "Loading…" : `${images.length} dataset images`}
            </p>
            <div className="grid grid-cols-[repeat(auto-fill,minmax(160px,1fr))] gap-3">
              {images.slice(0, visibleCount).map(img => (
                <motion.div
                  key={img.image_id}
                  onClick={() => setSelectedImage(img)}
                  whileHover={{ y: -3 }}
                  className={`rounded-xl overflow-hidden border bg-[var(--color-bg-card)] cursor-pointer transition-all duration-200 ${
                    selectedImage?.image_id === img.image_id
                      ? "border-[var(--color-accent)] shadow-lg shadow-blue-500/10"
                      : "border-[var(--color-border)] hover:border-[var(--color-border)]/80"
                  }`}
                >
                  <img src={api.imageUrl(img.id)} alt={img.image_id} className="w-full aspect-video object-cover" />
                  <div className="p-2.5">
                    <p className="text-[10px] font-mono font-bold text-[var(--color-accent-cyan)] truncate">{img.image_id}</p>
                    <span className={`inline-block mt-1.5 text-[10px] font-medium px-2 py-0.5 rounded-md ${
                      img.annotation_status === "Pending"
                        ? "bg-[var(--color-accent-amber)]/10 text-[var(--color-accent-amber)]"
                        : "bg-[var(--color-accent-green)]/10 text-[var(--color-accent-green)]"
                    }`}>
                      {img.annotation_status}
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

          {/* Detail Panel */}
          <AnimatePresence>
            {selectedImage && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="lg:w-80 shrink-0 rounded-xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-5 max-h-[75vh] overflow-auto"
              >
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-bold font-mono text-[var(--color-accent-cyan)]">{selectedImage.image_id}</h4>
                  <button onClick={() => setSelectedImage(null)} className="p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer bg-transparent border-none">
                    <X size={16} />
                  </button>
                </div>
                <img src={api.imageUrl(selectedImage.id)} alt={selectedImage.image_id} className="w-full rounded-lg mb-4" />
                <div className="space-y-1">
                  {[
                    { l: "Image ID", v: selectedImage.image_id, mono: true },
                    { l: "Sequence", v: selectedImage.sequence_id },
                    { l: "Subject", v: selectedImage.subject },
                    { l: "Board Type", v: selectedImage.board_type },
                    { l: "Writer", v: selectedImage.writer_id },
                    { l: "Frame Index", v: selectedImage.frame_index },
                    { l: "Timestamp", v: `${selectedImage.timestamp_ms}ms` },
                    { l: "Status", v: selectedImage.annotation_status, color: selectedImage.annotation_status === "Pending" ? "var(--color-accent-amber)" : "var(--color-accent-green)" },
                    { l: "Version", v: selectedImage.dataset_version },
                    { l: "Uploaded By", v: selectedImage.uploaded_by },
                    { l: "Created", v: selectedImage.created_at?.slice(0, 19) },
                    { l: "Storage Path", v: selectedImage.image_path, mono: true },
                  ].map(m => (
                    <div key={m.l} className="flex justify-between py-1.5 border-b border-[var(--color-border)]/50">
                      <span className="text-[11px] text-[var(--color-text-muted)]">{m.l}</span>
                      <span className={`text-[11px] max-w-[55%] truncate text-right ${m.mono ? "font-mono" : ""}`} style={{ color: m.color || "var(--color-text-secondary)" }}>{m.v}</span>
                    </div>
                  ))}
                </div>
                <button onClick={() => handleDeleteImage(selectedImage.image_id)} className="mt-4 w-full py-2 rounded-lg text-xs font-semibold border border-[var(--color-accent-rose)]/20 bg-[var(--color-accent-rose)]/8 text-[var(--color-accent-rose)] hover:bg-[var(--color-accent-rose)]/15 cursor-pointer transition-colors flex items-center justify-center gap-1.5">
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
