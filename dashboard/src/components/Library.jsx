import { useEffect, useState } from "react";
import { api } from "../api";

export default function Library({ refreshKey }) {
  const [videos, setVideos] = useState([]);
  const [selected, setSelected] = useState(null);
  const [keyframes, setKeyframes] = useState([]);
  const [idx, setIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  function selectVideo(id) {
    setSelected(id);
    setIdx(0);
    api.getKeyframes(id).then(setKeyframes);
  }

  useEffect(() => {
    setLoading(true);
    api.getVideos().then(vs => {
      setVideos(vs);
      if (vs.length) {
        setSelected(vs[0].id);
        setIdx(0);
        api.getKeyframes(vs[0].id).then(setKeyframes);
      }
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [refreshKey]);

  // Auto-refresh when videos are processing
  useEffect(() => {
    const isProcessing = videos.some(v => v.processing);
    if (!isProcessing) return;

    const interval = setInterval(() => {
      api.getVideos().then(vs => {
        setVideos(vs);
        const curVideo = vs.find(v => v.id === selected);
        if (curVideo && (curVideo.processing || keyframes.length === 0)) {
          api.getKeyframes(selected).then(kfs => {
            if (kfs.length !== keyframes.length) {
              setKeyframes(kfs);
            }
          });
        }
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [videos, selected, keyframes]);

  async function stopProcessing(id) {
    try {
      await api.stopVideo(id);
      api.getVideos().then(setVideos);
    } catch (err) {
      console.error(err);
    }
  }

  async function handleDelete(id) {
    await api.deleteVideo(id);
    const updated = videos.filter(v => v.id !== id);
    setVideos(updated);
    if (selected === id) {
      setKeyframes([]);
      setSelected(updated[0]?.id || null);
      if (updated[0]) api.getKeyframes(updated[0].id).then(setKeyframes);
    }
  }

  if (loading) return <p style={{ color: "#94a3b8" }}>Loading dataset…</p>;
  if (!videos.length) return <p style={{ color: "#94a3b8" }}>No videos yet. Upload one to start building the ECHD dataset.</p>;

  function downloadVideo(id) { window.open(api.videoZipUrl(id), "_blank"); }
  function downloadAll() { window.open(api.datasetZipUrl(), "_blank"); }

  const kf = keyframes[idx];
  const selectedVideo = videos.find(v => v.id === selected);

  return (
    <div style={styles.wrap}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        <h4 style={styles.sidebarTitle}>📁 Source Videos</h4>
        {videos.map(v => (
          <div key={v.id} onClick={() => selectVideo(v.id)}
            style={{ ...styles.videoItem, ...(selected === v.id ? styles.activeItem : {}) }}>
            <span style={styles.videoName}>{v.filename}</span>
            <span style={styles.meta}>
              {v.processing ? (
                <span style={{ color: "#38bdf8", fontWeight: 600 }}>⏳ Processing...</span>
              ) : (
                `${v.duration_sec.toFixed(1)}s · ${v.uploaded_at.slice(0, 10)}`
              )}
            </span>
            <button onClick={e => { e.stopPropagation(); handleDelete(v.id); }} style={styles.delBtn}>🗑</button>
          </div>
        ))}
      </div>

      {/* Main viewer */}
      <div style={styles.viewer}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h4 style={{ color: "#e2e8f0", margin: 0, fontSize: 15 }}>
            {keyframes.length > 0 ? `${keyframes.length} Dataset Images` : "Dataset Images"}
          </h4>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => downloadVideo(selected)} style={styles.dlBtnSm}>⬇️ This Sequence</button>
            <button onClick={downloadAll} style={styles.dlBtn}>⬇️ Full ECHD Dataset</button>
          </div>
        </div>

        {keyframes.length === 0 && (
          <div style={styles.emptyState}>
            <p style={{ color: selectedVideo?.processing ? "#38bdf8" : "#64748b", margin: 0, fontSize: 14 }}>
              {selectedVideo?.processing
                ? "⏳ Downloading and processing video... Dataset images will appear here automatically."
                : "No dataset images for this video."}
            </p>
            {selectedVideo?.processing && (
              <button onClick={() => stopProcessing(selectedVideo.id)} style={styles.stopBtn}>
                ⏹ Stop Processing
              </button>
            )}
          </div>
        )}

        {kf && (
          <>
            <img src={api.imageUrl(kf.id)} alt={`frame ${kf.frame_index}`} style={styles.img} />

            {/* Metadata panel */}
            <div style={styles.metaPanel}>
              <MetaItem label="ECHD ID" value={kf.image_id} highlight />
              <MetaItem label="Sequence" value={kf.sequence_id} />
              <MetaItem label="Subject" value={kf.subject} />
              <MetaItem label="Board" value={kf.board_type} />
              <MetaItem label="Writer" value={kf.writer_id} />
              <MetaItem label="Frame" value={kf.frame_index} />
              <MetaItem label="Time" value={`${kf.timestamp_ms}ms`} />
              <MetaItem label="Status" value={kf.annotation_status}
                color={kf.annotation_status === "Pending" ? "#f59e0b" : "#10b981"} />
              <MetaItem label="Version" value={kf.dataset_version} />
            </div>

            <input type="range" min={0} max={keyframes.length - 1} value={idx}
              onChange={e => setIdx(parseInt(e.target.value))} style={styles.timeline} />
            <p style={styles.counter}>{idx + 1} / {keyframes.length}</p>

            {/* Thumbnail Grid */}
            <div style={styles.grid}>
              {keyframes.map((k, i) => (
                <img key={k.id} src={api.imageUrl(k.id)} alt=""
                  onClick={() => setIdx(i)}
                  style={{ ...styles.thumb, ...(i === idx ? styles.activeThumb : {}) }} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MetaItem({ label, value, highlight, color }) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      <span style={{ fontSize: 11, color: "#64748b", minWidth: 60 }}>{label}:</span>
      <span style={{
        fontSize: 12,
        color: color || (highlight ? "#22d3ee" : "#cbd5e1"),
        fontWeight: highlight ? 700 : 400,
        fontFamily: highlight ? "monospace" : "inherit",
      }}>{value}</span>
    </div>
  );
}

const styles = {
  wrap: { display: "flex", gap: 20 },
  sidebar: { width: 240, display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 },
  sidebarTitle: { color: "#94a3b8", fontSize: 13, fontWeight: 600, margin: "0 0 8px 0" },
  videoItem: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 10, padding: "10px 12px",
    cursor: "pointer", position: "relative", display: "flex", flexDirection: "column", gap: 2,
    transition: "border-color 0.2s",
  },
  activeItem: { border: "2px solid #0ea5e9" },
  videoName: { fontSize: 13, color: "#e2e8f0", fontWeight: 600, wordBreak: "break-word" },
  meta: { fontSize: 11, color: "#64748b" },
  delBtn: { position: "absolute", top: 8, right: 8, background: "none", border: "none", cursor: "pointer", fontSize: 14 },
  viewer: { flex: 1 },
  img: { width: "100%", borderRadius: 12, maxHeight: 420, objectFit: "contain", background: "#0f172a", border: "1px solid #1e293b" },
  metaPanel: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
    gap: "6px 16px",
    background: "rgba(14, 165, 233, 0.06)",
    border: "1px solid #1e293b",
    borderRadius: 10,
    padding: "12px 16px",
    margin: "10px 0",
  },
  timeline: { width: "100%", margin: "4px 0" },
  counter: { color: "#64748b", fontSize: 12, textAlign: "right", margin: "2px 0 10px" },
  dlBtn: {
    padding: "7px 14px", borderRadius: 8, border: "none",
    background: "linear-gradient(135deg, #0ea5e9, #06b6d4)", color: "#fff",
    fontWeight: 600, cursor: "pointer", fontSize: 12,
  },
  dlBtnSm: {
    padding: "7px 14px", borderRadius: 8, border: "1px solid #334155",
    background: "#0f172a", color: "#94a3b8", cursor: "pointer", fontSize: 12,
  },
  emptyState: {
    display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start",
    padding: "28px 20px",
    background: "rgba(100, 116, 139, 0.06)",
    border: "1px dashed #334155",
    borderRadius: 12,
  },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))", gap: 6 },
  thumb: { width: "100%", aspectRatio: "16/9", objectFit: "cover", borderRadius: 6, cursor: "pointer", border: "2px solid transparent" },
  activeThumb: { border: "2px solid #0ea5e9" },
  stopBtn: {
    background: "#ef4444", color: "#fff", border: "none", borderRadius: 8,
    padding: "8px 16px", cursor: "pointer", fontSize: 13, fontWeight: 600,
  },
};
