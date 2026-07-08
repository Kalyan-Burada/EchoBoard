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

  if (loading) return <p style={{ color: "#94a3b8" }}>Loading library…</p>;
  if (!videos.length) return <p style={{ color: "#94a3b8" }}>No videos yet. Upload one first.</p>;

  // open URL directly — browser triggers file download
  function downloadVideo(id) { window.open(api.videoZipUrl(id), "_blank"); }
  function downloadAll() { window.open(api.datasetZipUrl(), "_blank"); }

  const kf = keyframes[idx];

  return (
    <div style={styles.wrap}>
      {/* Sidebar */}
      <div style={styles.sidebar}>
        {videos.map(v => (
          <div key={v.id} onClick={() => selectVideo(v.id)}
            style={{ ...styles.videoItem, ...(selected === v.id ? styles.activeItem : {}) }}>
            <span style={styles.videoName}>{v.filename}</span>
            <span style={styles.meta}>{v.duration_sec.toFixed(1)}s · {v.uploaded_at.slice(0, 10)}</span>
            <button onClick={e => { e.stopPropagation(); handleDelete(v.id); }} style={styles.delBtn}>🗑</button>
          </div>
        ))}
      </div>

      {/* Main viewer */}
      <div style={styles.viewer}>
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
          <button onClick={downloadAll} style={styles.dlBtn}>⬇️ Download Full Dataset (ZIP)</button>
        </div>
        {keyframes.length === 0 && <p style={{ color: "#94a3b8" }}>No keyframes.</p>}
        {kf && (
          <>
            <img src={api.imageUrl(kf.id)} alt={`frame ${kf.frame_number}`} style={styles.img} />
            <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "8px 0 4px" }}>
              <p style={styles.caption}>t = {kf.timestamp_sec}s · frame {kf.frame_number}</p>
              <button onClick={() => downloadVideo(selected)} style={styles.dlBtnSm}>⬇️ This video ZIP</button>
            </div>
            <input type="range" min={0} max={keyframes.length - 1} value={idx}
              onChange={e => setIdx(parseInt(e.target.value))} style={styles.timeline} />
            <p style={styles.counter}>{idx + 1} / {keyframes.length}</p>

            {/* Grid */}
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

const styles = {
  wrap: { display: "flex", gap: 20 },
  sidebar: { width: 240, display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 },
  videoItem: {
    background: "#1e293b", borderRadius: 10, padding: "10px 12px",
    cursor: "pointer", position: "relative", display: "flex", flexDirection: "column", gap: 2,
  },
  activeItem: { border: "2px solid #0ea5e9" },
  videoName: { fontSize: 13, color: "#e2e8f0", fontWeight: 600, wordBreak: "break-word" },
  meta: { fontSize: 11, color: "#64748b" },
  delBtn: { position: "absolute", top: 8, right: 8, background: "none", border: "none", cursor: "pointer", fontSize: 14 },
  viewer: { flex: 1 },
  img: { width: "100%", borderRadius: 10, maxHeight: 420, objectFit: "contain", background: "#0f172a" },
  caption: { color: "#94a3b8", fontSize: 13, margin: "8px 0 4px" },
  timeline: { width: "100%", margin: "4px 0" },
  counter: { color: "#64748b", fontSize: 12, textAlign: "right" },
  dlBtn: { padding: "8px 16px", borderRadius: 8, border: "none", background: "#0ea5e9", color: "#fff", fontWeight: 600, cursor: "pointer", fontSize: 13 },
  dlBtnSm: { padding: "4px 12px", borderRadius: 6, border: "none", background: "#334155", color: "#94a3b8", cursor: "pointer", fontSize: 12 },
  grid: { display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(100px, 1fr))", gap: 6, marginTop: 16 },
  thumb: { width: "100%", aspectRatio: "16/9", objectFit: "cover", borderRadius: 6, cursor: "pointer", border: "2px solid transparent" },
  activeThumb: { border: "2px solid #0ea5e9" },
};
