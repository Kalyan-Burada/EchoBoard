import { useState } from "react";
import { api } from "../api";

export default function UploadPanel({ onDone }) {
  const [mode, setMode] = useState("video");
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  // Processing params
  const [sampleN, setSampleN] = useState(3);
  const [motionT, setMotionT] = useState(0.03);
  const [stableN, setStableN] = useState(4);
  const [contentT, setContentT] = useState(0.05);
  const [url, setUrl] = useState("");

  // Dataset metadata
  const [subject, setSubject] = useState("Mathematics");
  const [boardType, setBoardType] = useState("Blackboard");
  const [writerId, setWriterId] = useState("teacher01");
  const [sequenceId, setSequenceId] = useState("");

  async function handleVideoUpload(e) {
    e.preventDefault();
    const file = e.target.elements.videoFile.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("subject", subject);
    fd.append("board_type", boardType);
    fd.append("writer_id", writerId);
    fd.append("sample_every_n_frames", sampleN);
    fd.append("motion_threshold", motionT);
    fd.append("stable_frames_required", stableN);
    fd.append("new_content_threshold", contentT);
    setLoading(true); setStatus(null);
    try {
      const res = await api.uploadVideo(fd);
      setStatus({ ok: true, msg: `✅ ${res.keyframes_captured} keyframes captured → sequence "${res.sequence_id}"` });
      onDone();
    } catch { setStatus({ ok: false, msg: "Upload failed." }); }
    setLoading(false);
  }

  async function handleImagesUpload(e) {
    e.preventDefault();
    const files = e.target.elements.imgFiles.files;
    if (!files.length) return;
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
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

  async function handleUrlUpload(e) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true); setStatus(null);
    try {
      const res = await api.uploadUrl({
        url,
        subject,
        board_type: boardType,
        writer_id: writerId,
        sample_every_n_frames: sampleN,
        motion_threshold: motionT,
        stable_frames_required: stableN,
        new_content_threshold: contentT,
      });
      setStatus({ ok: true, msg: `✅ "${res.title}" is downloading & processing in the background!` });
      setTimeout(() => { onDone(); }, 1000);
    } catch {
      setStatus({ ok: false, msg: "Processing failed." });
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrap}>
      {/* Upload mode tabs */}
      <div style={styles.tabs}>
        {["video", "images", "url"].map(m => (
          <button key={m} onClick={() => setMode(m)}
            style={{ ...styles.tab, ...(mode === m ? styles.activeTab : {}) }}>
            {m === "video" ? "📹 Video" : m === "images" ? "🖼️ Images" : "🔗 URL"}
          </button>
        ))}
      </div>

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
          {mode === "images" && (
            <div style={styles.field}>
              <label style={styles.label}>Sequence ID (optional)</label>
              <input value={sequenceId} onChange={e => setSequenceId(e.target.value)}
                placeholder="e.g. math001" style={styles.input} />
            </div>
          )}
        </div>
      </div>

      {/* Upload Forms */}
      {mode === "video" && (
        <form onSubmit={handleVideoUpload} style={styles.form}>
          <input name="videoFile" type="file" accept=".mp4,.avi,.mov,.mkv,.webm" style={styles.fileInput} />
          <ParamSliders {...{ sampleN, setSampleN, motionT, setMotionT, stableN, setStableN, contentT, setContentT }} />
          <button type="submit" style={styles.btn} disabled={loading}>{loading ? "Processing…" : "Process Video"}</button>
        </form>
      )}

      {mode === "images" && (
        <form onSubmit={handleImagesUpload} style={styles.form}>
          <input name="imgFiles" type="file" accept=".jpg,.jpeg,.png,.bmp,.webp" multiple style={styles.fileInput} />
          <button type="submit" style={styles.btn} disabled={loading}>{loading ? "Storing…" : "Store Images"}</button>
        </form>
      )}

      {mode === "url" && (
        <form onSubmit={handleUrlUpload} style={styles.form}>
          <input value={url} onChange={e => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=…" style={styles.input} />
          <ParamSliders {...{ sampleN, setSampleN, motionT, setMotionT, stableN, setStableN, contentT, setContentT }} />
          <button type="submit" style={styles.btn} disabled={loading}>{loading ? "Processing…" : "Download & Process"}</button>
        </form>
      )}

      {status && (
        <p style={{ ...styles.status, color: status.ok ? "#10b981" : "#ef4444" }}>{status.msg}</p>
      )}
    </div>
  );
}

function ParamSliders({ sampleN, setSampleN, motionT, setMotionT, stableN, setStableN, contentT, setContentT }) {
  return (
    <div style={styles.sliders}>
      <h4 style={styles.sectionTitle}>⚙️ Keyframe Detection Parameters</h4>
      <SliderRow label={`Sample every ${sampleN} frames`} min={1} max={30} step={1} value={sampleN} onChange={setSampleN} />
      <SliderRow label={`Motion threshold: ${motionT}`} min={0.005} max={0.5} step={0.005} value={motionT} onChange={setMotionT} />
      <SliderRow label={`Stable frames required: ${stableN}`} min={1} max={20} step={1} value={stableN} onChange={setStableN} />
      <SliderRow label={`New-content threshold: ${contentT}`} min={0.01} max={2} step={0.01} value={contentT} onChange={setContentT} />
    </div>
  );
}

function SliderRow({ label, min, max, step, value, onChange }) {
  return (
    <div style={styles.sliderRow}>
      <span style={styles.sliderLabel}>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))} style={{ flex: 1, accentColor: "#0ea5e9" }} />
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
