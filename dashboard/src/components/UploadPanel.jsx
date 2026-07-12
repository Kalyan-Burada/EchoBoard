import { useState } from "react";
import { api } from "../api";

export default function UploadPanel({ onDone }) {
  // Dataset metadata
  const [subject, setSubject] = useState("Mathematics");
  const [boardType, setBoardType] = useState("Blackboard");
  const [writerId, setWriterId] = useState("teacher01");
  const [sequenceId, setSequenceId] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);

  async function handleImagesUpload(e) {
    e.preventDefault();
    const files = e.target.elements.imgFiles.files;
    if (!files.length) return;
    const fd = new FormData();
    for (const f of files) {
      // Filter out non-image files if they accidentally select a folder with other stuff
      if (f.type.startsWith("image/")) {
        fd.append("files", f);
      }
    }
    
    if (!fd.has("files")) {
      setStatus({ ok: false, msg: "No valid images found in the selected folder." });
      return;
    }

    fd.append("subject", subject);
    fd.append("board_type", boardType);
    fd.append("writer_id", writerId);
    if (sequenceId) fd.append("sequence_id", sequenceId);
    setLoading(true); setStatus(null);
    try {
      const res = await api.uploadImages(fd);
      setStatus({ ok: true, msg: `✅ ${res.images_stored} images stored → sequence "${res.sequence_id}"` });
      onDone();
    } catch { setStatus({ ok: false, msg: "Upload failed." }); }
    setLoading(false);
  }

  return (
    <div style={styles.wrap}>
      {/* Dataset Metadata Fields */}
      <div style={styles.metaSection}>
        <h4 style={styles.sectionTitle}>📋 Dataset Metadata</h4>
        <div style={styles.metaGrid}>
          <div style={styles.field}>
            <label style={styles.label}>Subject</label>
            <select value={subject} onChange={e => setSubject(e.target.value)} style={styles.select}>
              <option>Mathematics</option>
              <option>Physics</option>
              <option>Chemistry</option>
              <option>Biology</option>
              <option>Computer Science</option>
              <option>General</option>
            </select>
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Board Type</label>
            <select value={boardType} onChange={e => setBoardType(e.target.value)} style={styles.select}>
              <option>Blackboard</option>
              <option>Whiteboard</option>
            </select>
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Writer ID</label>
            <input value={writerId} onChange={e => setWriterId(e.target.value)}
              placeholder="e.g. teacher01" style={styles.input} />
          </div>
          <div style={styles.field}>
            <label style={styles.label}>Sequence ID (optional)</label>
            <input value={sequenceId} onChange={e => setSequenceId(e.target.value)}
              placeholder="e.g. math001" style={styles.input} />
          </div>
        </div>
      </div>

      {/* Upload Forms */}
      <form onSubmit={handleImagesUpload} style={styles.form}>
        <label style={styles.label}>Select a folder containing images to upload:</label>
        <input name="imgFiles" type="file" accept="image/*" multiple webkitdirectory="true" directory="true" style={styles.fileInput} />
        <button type="submit" style={styles.btn} disabled={loading}>{loading ? "Storing Folder in MinIO…" : "Upload Entire Folder"}</button>
      </form>

      {status && (
        <p style={{ ...styles.status, color: status.ok ? "#10b981" : "#ef4444" }}>{status.msg}</p>
      )}
    </div>
  );
}

const styles = {
  wrap: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 14,
    padding: "24px 28px",
  },
  tabs: { display: "flex", gap: 8, marginBottom: 20 },
  tab: {
    padding: "8px 20px", borderRadius: 8, border: "1px solid #334155",
    background: "#0f172a", color: "#94a3b8", cursor: "pointer", fontSize: 13, fontWeight: 500,
    transition: "all 0.2s",
  },
  activeTab: { background: "#0ea5e9", color: "#fff", fontWeight: 600, borderColor: "#0ea5e9" },
  metaSection: {
    background: "rgba(14, 165, 233, 0.06)",
    border: "1px solid #1e293b",
    borderRadius: 10,
    padding: "16px 18px",
    marginBottom: 18,
  },
  sectionTitle: { color: "#94a3b8", fontSize: 13, fontWeight: 600, margin: "0 0 12px 0", letterSpacing: "0.3px" },
  metaGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 16px" },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  label: { fontSize: 12, color: "#64748b", fontWeight: 500 },
  select: {
    background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13,
  },
  input: {
    background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13, width: "100%",
  },
  fileInput: {
    background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
    borderRadius: 6, padding: "8px 10px", fontSize: 13, width: "100%",
  },
  form: { display: "flex", flexDirection: "column", gap: 14 },
  btn: {
    padding: "10px 24px", borderRadius: 8, border: "none",
    background: "linear-gradient(135deg, #0ea5e9, #06b6d4)", color: "#fff",
    fontWeight: 600, cursor: "pointer", fontSize: 14,
    transition: "opacity 0.2s",
  },
  sliders: {
    background: "rgba(100, 116, 139, 0.08)",
    border: "1px solid #1e293b",
    borderRadius: 10,
    padding: "14px 16px",
  },
  sliderRow: { display: "flex", alignItems: "center", gap: 10, marginBottom: 6 },
  sliderLabel: { fontSize: 12, color: "#94a3b8", minWidth: 180 },
  status: { marginTop: 14, fontSize: 14, fontWeight: 500 },
};
