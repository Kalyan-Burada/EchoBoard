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
      <Stat label="Videos" value={stats.total_videos} />
      <Stat label="Keyframes" value={stats.total_keyframes} />
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div style={styles.card}>
      <span style={styles.value}>{value}</span>
      <span style={styles.label}>{label}</span>
    </div>
  );
}

const styles = {
  bar: { display: "flex", gap: 16, marginBottom: 24 },
  card: {
    background: "#1e293b", borderRadius: 10, padding: "16px 28px",
    display: "flex", flexDirection: "column", alignItems: "center",
  },
  value: { fontSize: 28, fontWeight: 700, color: "#38bdf8" },
  label: { fontSize: 13, color: "#94a3b8", marginTop: 2 },
};
