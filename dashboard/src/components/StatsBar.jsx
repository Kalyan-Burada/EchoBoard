import { useEffect, useState } from "react";
import { api } from "../api";

export default function StatsBar() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  return (
    <div style={styles.bar}>
      <Stat label="Videos" value={stats.total_videos} icon="🎥" color="#0ea5e9" />
      <Stat label="Dataset Images" value={stats.total_images} icon="🖼️" color="#22d3ee" />
      <Stat label="Pending" value={stats.pending_annotations} icon="⏳" color="#f59e0b" />
      <Stat label="Annotated" value={stats.completed_annotations} icon="✅" color="#10b981" />
      <Stat label="Version" value={stats.current_version} icon="📦" color="#a78bfa" isText />
    </div>
  );
}

function Stat({ label, value, icon, color, isText }) {
  return (
    <div style={styles.card}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <span style={{ ...styles.value, color, fontSize: isText ? 16 : 28 }}>{value}</span>
      <span style={styles.label}>{label}</span>
    </div>
  );
}

const styles = {
  bar: { display: "flex", gap: 14, marginBottom: 24, flexWrap: "wrap" },
  card: {
    background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
    border: "1px solid #1e293b",
    borderRadius: 12,
    padding: "14px 22px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 4,
    minWidth: 110,
    flex: 1,
    transition: "transform 0.2s, box-shadow 0.2s",
  },
  value: { fontSize: 28, fontWeight: 700 },
  label: { fontSize: 12, color: "#64748b", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.5px" },
};
