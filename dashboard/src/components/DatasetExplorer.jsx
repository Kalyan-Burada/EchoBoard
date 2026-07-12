import { useEffect, useState } from "react";
import { api } from "../api";

export default function DatasetExplorer({ refreshKey }) {
  const [images, setImages] = useState([]);
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(null);

  // Filters
  const [filterSubject, setFilterSubject] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterVersion, setFilterVersion] = useState("");
  const [filterWriter, setFilterWriter] = useState("");

  // Version creation
  const [newVersionDesc, setNewVersionDesc] = useState("");
  const [versionMsg, setVersionMsg] = useState(null);

  function loadImages() {
    setLoading(true);
    const params = {};
    if (filterSubject) params.subject = filterSubject;
    if (filterStatus) params.annotation_status = filterStatus;
    if (filterVersion) params.dataset_version = filterVersion;
    if (filterWriter) params.writer_id = filterWriter;
    api.getDatasetImages(params).then(imgs => {
      setImages(imgs);
      setLoading(false);
    }).catch(() => setLoading(false));
  }

  function loadVersions() {
    api.getVersions().then(setVersions).catch(() => {});
  }

  useEffect(() => {
    loadImages();
    loadVersions();
  }, [refreshKey, filterSubject, filterStatus, filterVersion, filterWriter]);

  async function handleCreateVersion() {
    try {
      const res = await api.createVersion(newVersionDesc);
      setVersionMsg(`✅ Created ${res.version}`);
      setNewVersionDesc("");
      loadVersions();
    } catch {
      setVersionMsg("❌ Failed to create version");
    }
  }

  async function handleDeleteImage(imageId) {
    await api.deleteDatasetImage(imageId);
    setImages(prev => prev.filter(i => i.image_id !== imageId));
    if (selectedImage?.image_id === imageId) setSelectedImage(null);
  }

  // Unique subjects and writers from current dataset
  const subjects = [...new Set(images.map(i => i.subject))];
  const writers = [...new Set(images.map(i => i.writer_id))];

  return (
    <div style={styles.wrap}>
      {/* Filters Bar */}
      <div style={styles.filterBar}>
        <h4 style={styles.sectionTitle}>🔍 Filter Dataset</h4>
        <div style={styles.filters}>
          <select value={filterSubject} onChange={e => setFilterSubject(e.target.value)} style={styles.select}>
            <option value="">All Subjects</option>
            {subjects.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={styles.select}>
            <option value="">All Status</option>
            <option value="Pending">⏳ Pending</option>
            <option value="Completed">✅ Completed</option>
          </select>
          <select value={filterVersion} onChange={e => setFilterVersion(e.target.value)} style={styles.select}>
            <option value="">All Versions</option>
            {versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
          </select>
          <select value={filterWriter} onChange={e => setFilterWriter(e.target.value)} style={styles.select}>
            <option value="">All Writers</option>
            {writers.map(w => <option key={w} value={w}>{w}</option>)}
          </select>
          <button onClick={loadImages} style={styles.refreshBtn}>🔄</button>
        </div>
      </div>

      {/* Main layout */}
      <div style={styles.mainLayout}>
        {/* Image grid */}
        <div style={styles.gridSection}>
          <p style={styles.resultCount}>
            {loading ? "Loading..." : `${images.length} dataset images`}
          </p>
          <div style={styles.grid}>
            {images.map(img => (
              <div key={img.image_id}
                onClick={() => setSelectedImage(img)}
                style={{
                  ...styles.card,
                  ...(selectedImage?.image_id === img.image_id ? styles.activeCard : {}),
                }}>
                <img src={api.imageUrl(img.id)} alt={img.image_id} style={styles.cardImg} />
                <div style={styles.cardInfo}>
                  <span style={styles.echdId}>{img.image_id}</span>
                  <span style={{
                    ...styles.statusBadge,
                    background: img.annotation_status === "Pending" ? "rgba(245, 158, 11, 0.15)" : "rgba(16, 185, 129, 0.15)",
                    color: img.annotation_status === "Pending" ? "#f59e0b" : "#10b981",
                  }}>
                    {img.annotation_status === "Pending" ? "⏳" : "✅"} {img.annotation_status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selectedImage && (
          <div style={styles.detailPanel}>
            <h4 style={styles.detailTitle}>{selectedImage.image_id}</h4>
            <img src={api.imageUrl(selectedImage.id)} alt={selectedImage.image_id} style={styles.detailImg} />
            <div style={styles.detailMeta}>
              <MetaRow label="Image ID" value={selectedImage.image_id} mono />
              <MetaRow label="Sequence" value={selectedImage.sequence_id} />
              <MetaRow label="Subject" value={selectedImage.subject} />
              <MetaRow label="Board Type" value={selectedImage.board_type} />
              <MetaRow label="Writer" value={selectedImage.writer_id} />
              <MetaRow label="Frame Index" value={selectedImage.frame_index} />
              <MetaRow label="Timestamp" value={`${selectedImage.timestamp_ms}ms`} />
              <MetaRow label="Status" value={selectedImage.annotation_status}
                color={selectedImage.annotation_status === "Pending" ? "#f59e0b" : "#10b981"} />
              <MetaRow label="Version" value={selectedImage.dataset_version} />
              <MetaRow label="Uploaded By" value={selectedImage.uploaded_by} />
              <MetaRow label="Created" value={selectedImage.created_at?.slice(0, 19)} />
              <MetaRow label="Storage Path" value={selectedImage.image_path} mono />
            </div>
            <button onClick={() => handleDeleteImage(selectedImage.image_id)} style={styles.deleteBtn}>
              🗑 Delete Image
            </button>
          </div>
        )}
      </div>

      {/* Version Management */}
      <div style={styles.versionSection}>
        <h4 style={styles.sectionTitle}>📦 Dataset Versions</h4>
        <div style={styles.versionGrid}>
          {versions.map(v => (
            <div key={v.version} style={styles.versionCard}>
              <span style={styles.versionName}>{v.version}</span>
              <span style={styles.versionMeta}>{v.image_count} images · {v.created_at?.slice(0, 10)}</span>
              {v.description && <span style={styles.versionDesc}>{v.description}</span>}
            </div>
          ))}
          {versions.length === 0 && (
            <p style={{ color: "#64748b", fontSize: 13, margin: 0 }}>No versions created yet. Images default to ECHD_v1.</p>
          )}
        </div>
        <div style={styles.createVersion}>
          <input value={newVersionDesc} onChange={e => setNewVersionDesc(e.target.value)}
            placeholder="Version description (optional)" style={styles.versionInput} />
          <button onClick={handleCreateVersion} style={styles.createBtn}>Create New Version</button>
        </div>
        {versionMsg && <p style={{ fontSize: 13, color: "#10b981", marginTop: 8 }}>{versionMsg}</p>}
      </div>
    </div>
  );
}

function MetaRow({ label, value, mono, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", borderBottom: "1px solid #1e293b" }}>
      <span style={{ fontSize: 12, color: "#64748b" }}>{label}</span>
      <span style={{
        fontSize: 12,
        color: color || "#cbd5e1",
        fontFamily: mono ? "monospace" : "inherit",
        maxWidth: 180,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        textAlign: "right",
      }}>{value}</span>
    </div>
  );
}

const styles = {
  wrap: { display: "flex", flexDirection: "column", gap: 20 },
  filterBar: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 12,
    padding: "16px 20px",
  },
  sectionTitle: { color: "#94a3b8", fontSize: 13, fontWeight: 600, margin: "0 0 10px 0" },
  filters: { display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" },
  select: {
    background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 12,
  },
  refreshBtn: {
    background: "#0f172a", border: "1px solid #334155", borderRadius: 6,
    padding: "7px 12px", cursor: "pointer", fontSize: 14,
  },
  mainLayout: { display: "flex", gap: 20 },
  gridSection: { flex: 1 },
  resultCount: { color: "#64748b", fontSize: 13, margin: "0 0 10px 0" },
  grid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
    gap: 10,
  },
  card: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 10,
    overflow: "hidden",
    cursor: "pointer",
    transition: "border-color 0.2s, transform 0.15s",
  },
  activeCard: { borderColor: "#0ea5e9", transform: "scale(1.02)" },
  cardImg: { width: "100%", aspectRatio: "16/9", objectFit: "cover" },
  cardInfo: { padding: "6px 8px", display: "flex", flexDirection: "column", gap: 3 },
  echdId: { fontSize: 11, color: "#22d3ee", fontFamily: "monospace", fontWeight: 600 },
  statusBadge: {
    fontSize: 10, borderRadius: 4, padding: "2px 6px",
    display: "inline-block", width: "fit-content",
  },
  detailPanel: {
    width: 300,
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 12,
    padding: "16px",
    flexShrink: 0,
    maxHeight: "70vh",
    overflow: "auto",
  },
  detailTitle: { color: "#22d3ee", fontSize: 15, fontWeight: 700, fontFamily: "monospace", margin: "0 0 10px 0" },
  detailImg: { width: "100%", borderRadius: 8, marginBottom: 12 },
  detailMeta: { display: "flex", flexDirection: "column", gap: 2 },
  deleteBtn: {
    marginTop: 14, width: "100%", padding: "8px", borderRadius: 8,
    border: "1px solid #ef4444", background: "rgba(239, 68, 68, 0.1)",
    color: "#ef4444", cursor: "pointer", fontSize: 13, fontWeight: 600,
  },
  versionSection: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 12,
    padding: "16px 20px",
  },
  versionGrid: { display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 14 },
  versionCard: {
    background: "rgba(167, 139, 250, 0.08)",
    border: "1px solid #334155",
    borderRadius: 8,
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column",
    gap: 3,
    minWidth: 140,
  },
  versionName: { fontSize: 14, fontWeight: 700, color: "#a78bfa" },
  versionMeta: { fontSize: 11, color: "#64748b" },
  versionDesc: { fontSize: 11, color: "#94a3b8", fontStyle: "italic" },
  createVersion: { display: "flex", gap: 10 },
  versionInput: {
    flex: 1, background: "#0f172a", color: "#e2e8f0", border: "1px solid #334155",
    borderRadius: 6, padding: "7px 10px", fontSize: 13,
  },
  createBtn: {
    padding: "8px 18px", borderRadius: 8, border: "none",
    background: "linear-gradient(135deg, #a78bfa, #7c3aed)", color: "#fff",
    fontWeight: 600, cursor: "pointer", fontSize: 13,
  },
};
