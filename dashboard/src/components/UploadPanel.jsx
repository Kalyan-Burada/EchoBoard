import { useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { FolderUp, Upload, CheckCircle2, AlertCircle, Image, Tag } from "lucide-react";
import { api } from "../api";

const CLASSES = ["Text", "Equation", "Heading", "Diagram", "Table", "Other"];

export default function UploadPanel({ onDone }) {
  const [folderName, setFolderName] = useState("Lecture_01");
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [annotations, setAnnotations] = useState({});
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef(null);

  function handleFolderSelect(e) {
    const files = Array.from(e.target.files).filter((f) =>
      f.type.startsWith("image/")
    );
    if (!files.length) {
      setStatus({ ok: false, msg: "No valid images found in selected folder." });
      return;
    }
    setSelectedFiles(files);
    setStatus(null);
    const annMap = {};
    files.forEach((f) => {
      annMap[f.name] = { text: "", class: "Text" };
    });
    setAnnotations(annMap);
  }

  function updateAnnotation(filename, field, value) {
    setAnnotations((prev) => ({
      ...prev,
      [filename]: { ...prev[filename], [field]: value },
    }));
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!selectedFiles.length) return;

    const fd = new FormData();
    selectedFiles.forEach((f) => fd.append("files", f));
    fd.append("folder_name", folderName);
    fd.append("annotations_json", JSON.stringify(annotations));

    setLoading(true);
    setStatus(null);
    setProgress(0);

    try {
      const res = await api.uploadImages(fd);
      setStatus({
        ok: true,
        msg: `${res.images_stored} images uploaded to MinIO & MongoDB → folder "${res.folder_name}"`,
      });
      setSelectedFiles([]);
      setAnnotations({});
      if (fileInputRef.current) fileInputRef.current.value = "";
      onDone();
    } catch {
      setStatus({ ok: false, msg: "Upload failed. Check backend logs." });
    }
    setLoading(false);
  }

  return (
    <section id="upload" className="py-28 px-6 sm:px-10 lg:px-16">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-12"
        >
          <p className="text-sm font-bold tracking-widest uppercase mb-4"
            style={{ background: "linear-gradient(135deg, #3B82F6, #8B5CF6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Upload</p>
          <h2 className="block text-3xl sm:text-4xl lg:text-5xl font-bold text-[var(--color-text-primary)] mb-5 leading-tight">Dataset Upload</h2>
          <p className="text-[var(--color-text-muted)] text-sm sm:text-base max-w-lg mx-auto leading-relaxed">Upload whiteboard images to build the ECHD dataset. Annotate each image with visible text and content class.</p>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="rounded-2xl border border-[var(--color-border)] bg-[var(--color-bg-card)] p-6 sm:p-8 space-y-6"
        >
          {/* Folder Name Input */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
              Folder Name (MinIO path)
            </label>
            <input
              value={folderName}
              onChange={(e) => setFolderName(e.target.value)}
              placeholder="e.g. Lecture_01"
              className="w-full px-4 py-2.5 rounded-xl bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-sm focus:border-[var(--color-accent)] focus:outline-none transition-colors"
            />
          </div>

          {/* Drop Zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="relative border-2 border-dashed border-[var(--color-border)] rounded-xl p-10 text-center cursor-pointer hover:border-[var(--color-accent)]/40 transition-colors group"
          >
            <FolderUp size={32} className="mx-auto mb-3 text-[var(--color-text-muted)] group-hover:text-[var(--color-accent)] transition-colors" />
            <p className="text-sm font-medium text-[var(--color-text-secondary)] mb-1">
              Click to select a folder of images
            </p>
            <p className="text-xs text-[var(--color-text-muted)]">Supports JPG, PNG, WebP</p>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              webkitdirectory="true"
              directory="true"
              onChange={handleFolderSelect}
              className="hidden"
            />
          </div>

          {/* Annotation Table */}
          <AnimatePresence>
            {selectedFiles.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="space-y-4 overflow-hidden"
              >
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-[var(--color-text-secondary)] flex items-center gap-2">
                    <Tag size={14} />
                    Annotate Images
                    <span className="text-xs font-normal text-[var(--color-text-muted)]">
                      ({selectedFiles.length} selected)
                    </span>
                  </h3>
                </div>
                <p className="text-xs text-[var(--color-text-muted)]">
                  Enter visible text on the board for each image. Leave blank to skip annotation.
                </p>

                <div className="max-h-96 overflow-auto rounded-xl border border-[var(--color-border)]">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-[var(--color-bg-primary)]">
                        <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider sticky top-0 bg-[var(--color-bg-primary)] z-10 border-b border-[var(--color-border)]">#</th>
                        <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider sticky top-0 bg-[var(--color-bg-primary)] z-10 border-b border-[var(--color-border)]">Preview</th>
                        <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider sticky top-0 bg-[var(--color-bg-primary)] z-10 border-b border-[var(--color-border)]">Filename</th>
                        <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider sticky top-0 bg-[var(--color-bg-primary)] z-10 border-b border-[var(--color-border)] min-w-[220px]">Board Text</th>
                        <th className="px-3 py-2.5 text-left text-[10px] font-semibold text-[var(--color-text-muted)] uppercase tracking-wider sticky top-0 bg-[var(--color-bg-primary)] z-10 border-b border-[var(--color-border)]">Class</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedFiles.map((file, idx) => (
                        <tr key={file.name} className="border-b border-[var(--color-border)]/30 hover:bg-[var(--color-bg-card-hover)] transition-colors">
                          <td className="px-3 py-2 text-xs text-[var(--color-text-muted)]">{idx + 1}</td>
                          <td className="px-3 py-2">
                            <img
                              src={URL.createObjectURL(file)}
                              alt={file.name}
                              className="w-12 h-8 object-cover rounded border border-[var(--color-border)]"
                            />
                          </td>
                          <td className="px-3 py-2 text-xs text-[var(--color-text-muted)] max-w-[140px] truncate">{file.name}</td>
                          <td className="px-3 py-2">
                            <input
                              value={annotations[file.name]?.text || ""}
                              onChange={(e) => updateAnnotation(file.name, "text", e.target.value)}
                              placeholder="e.g. x² + y² = r²"
                              className="w-full px-3 py-1.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs focus:border-[var(--color-accent)] focus:outline-none transition-colors"
                            />
                          </td>
                          <td className="px-3 py-2">
                            <select
                              value={annotations[file.name]?.class || "Text"}
                              onChange={(e) => updateAnnotation(file.name, "class", e.target.value)}
                              className="px-2 py-1.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-[var(--color-text-primary)] text-xs focus:border-[var(--color-accent)] focus:outline-none transition-colors"
                            >
                              {CLASSES.map((c) => (
                                <option key={c}>{c}</option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Upload Button */}
                <motion.button
                  onClick={handleUpload}
                  disabled={loading}
                  whileHover={!loading ? { scale: 1.01 } : {}}
                  whileTap={!loading ? { scale: 0.99 } : {}}
                  className={`w-full py-3 rounded-xl font-semibold text-sm text-white flex items-center justify-center gap-2 border-none cursor-pointer transition-all ${
                    loading
                      ? "bg-[var(--color-text-muted)] cursor-not-allowed"
                      : "bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent-cyan)] shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30"
                  }`}
                >
                  <Upload size={16} />
                  {loading ? "Uploading to MinIO & MongoDB…" : `Upload ${selectedFiles.length} Images`}
                </motion.button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Status Message */}
          <AnimatePresence>
            {status && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className={`flex items-center gap-2.5 p-4 rounded-xl text-sm font-medium border ${
                  status.ok
                    ? "bg-[var(--color-accent-green)]/8 border-[var(--color-accent-green)]/20 text-[var(--color-accent-green)]"
                    : "bg-[var(--color-accent-rose)]/8 border-[var(--color-accent-rose)]/20 text-[var(--color-accent-rose)]"
                }`}
              >
                {status.ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                {status.msg}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </section>
  );
}
