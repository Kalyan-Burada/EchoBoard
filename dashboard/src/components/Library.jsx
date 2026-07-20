import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Trash2, Download, StopCircle, FolderOpen, ChevronLeft, ChevronRight } from "lucide-react";
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

  useEffect(() => {
    const isProcessing = videos.some(v => v.processing);
    if (!isProcessing) return;
    const interval = setInterval(() => {
      api.getVideos().then(vs => {
        setVideos(vs);
        const curVideo = vs.find(v => v.id === selected);
        if (curVideo && (curVideo.processing || keyframes.length === 0)) {
          api.getKeyframes(selected).then(kfs => {
            if (kfs.length !== keyframes.length) setKeyframes(kfs);
          });
        }
      });
    }, 3000);
    return () => clearInterval(interval);
  }, [videos, selected, keyframes]);

  async function stopProcessing(id) {
    try { await api.stopVideo(id); api.getVideos().then(setVideos); } catch (err) { console.error(err); }
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

  function downloadVideo(id) { window.open(api.videoZipUrl(id), "_blank"); }
  function downloadAll() { window.open(api.datasetZipUrl(), "_blank"); }

  const kf = keyframes[idx];
  const selectedVideo = videos.find(v => v.id === selected);

  if (loading) return (
    <div className="py-24 px-6 text-center">
      <div className="w-6 h-6 border-2 border-[var(--color-accent)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
      <p className="text-sm text-[var(--color-text-muted)]">Loading dataset…</p>
    </div>
  );

  if (!videos.length) return null;

  return (
    <div className="py-8 flex gap-5 flex-col lg:flex-row">
      {/* Sidebar */}
      <div className="lg:w-60 shrink-0 space-y-2">
        <h4 className="text-xs font-semibold text-[var(--color-text-muted)] uppercase tracking-wider mb-3">Source Videos</h4>
        {videos.map(v => (
          <motion.div
            key={v.id}
            onClick={() => selectVideo(v.id)}
            whileHover={{ x: 2 }}
            className={`relative p-3 rounded-xl cursor-pointer transition-all duration-200 ${
              selected === v.id
                ? "bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30"
                : "border border-[var(--color-border)] bg-[var(--color-bg-card)] hover:border-[var(--color-border)]/80"
            }`}
          >
            <p className="text-sm font-medium text-[var(--color-text-primary)] pr-6 truncate">{v.filename}</p>
            <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
              {v.processing ? (
                <span className="text-[var(--color-accent)] font-semibold">⏳ Processing…</span>
              ) : v.fps === 0 ? (
                `${v.total_frames} images · ${(v.uploaded_at || "").slice(0, 10)}`
              ) : (
                `${(v.duration_sec || 0).toFixed(1)}s · ${(v.uploaded_at || "").slice(0, 10)}`
              )}
            </p>
            <button
              onClick={e => { e.stopPropagation(); handleDelete(v.id); }}
              className="absolute top-3 right-3 p-1 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-accent-rose)] hover:bg-[var(--color-accent-rose)]/10 transition-colors cursor-pointer bg-transparent border-none"
            >
              <Trash2 size={13} />
            </button>
          </motion.div>
        ))}
      </div>

      {/* Main Viewer */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-[var(--color-text-primary)]">
            {keyframes.length > 0 ? `${keyframes.length} Dataset Images` : "Dataset Images"}
          </h4>
          <div className="flex gap-2">
            <button onClick={() => downloadVideo(selected)} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] transition-colors cursor-pointer">
              <Download size={13} /> Sequence
            </button>
            <button onClick={downloadAll} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-[var(--color-accent)] to-[var(--color-accent-cyan)] text-white border-none cursor-pointer">
              <Download size={13} /> Full Dataset
            </button>
          </div>
        </div>

        {keyframes.length === 0 && (
          <div className="border border-dashed border-[var(--color-border)] rounded-xl p-8 text-center">
            <p className="text-sm text-[var(--color-text-muted)]">
              {selectedVideo?.processing ? "Processing… images will appear automatically." : "No images for this video."}
            </p>
            {selectedVideo?.processing && (
              <button onClick={() => stopProcessing(selectedVideo.id)} className="mt-3 px-4 py-2 rounded-lg text-xs font-semibold bg-[var(--color-accent-rose)]/10 text-[var(--color-accent-rose)] border border-[var(--color-accent-rose)]/20 cursor-pointer hover:bg-[var(--color-accent-rose)]/20 transition-colors">
                <StopCircle size={13} className="inline mr-1" /> Stop Processing
              </button>
            )}
          </div>
        )}

        {kf && (
          <>
            <div className="rounded-xl overflow-hidden border border-[var(--color-border)] bg-[var(--color-bg-primary)] mb-3">
              <img src={api.imageUrl(kf.id)} alt={`frame ${kf.frame_index}`} className="w-full max-h-[420px] object-contain" />
            </div>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mb-3">
              {[
                { l: "ECHD ID", v: kf.image_id, accent: true },
                { l: "Sequence", v: kf.sequence_id },
                { l: "Subject", v: kf.subject },
                { l: "Board", v: kf.board_type },
                { l: "Writer", v: kf.writer_id },
                { l: "Frame", v: kf.frame_index },
                { l: "Time", v: `${kf.timestamp_ms}ms` },
                { l: "Status", v: kf.annotation_status, color: kf.annotation_status === "Pending" ? "var(--color-accent-amber)" : "var(--color-accent-green)" },
              ].map(m => (
                <div key={m.l} className="px-3 py-2 rounded-lg bg-[var(--color-bg-card)] border border-[var(--color-border)]">
                  <p className="text-[10px] text-[var(--color-text-muted)] uppercase tracking-wider">{m.l}</p>
                  <p className={`text-xs font-medium mt-0.5 truncate ${m.accent ? "text-[var(--color-accent-cyan)] font-mono font-bold" : ""}`} style={m.color ? { color: m.color } : {}}>{m.v}</p>
                </div>
              ))}
            </div>

            {/* Timeline */}
            <div className="flex items-center gap-3 mb-3">
              <button onClick={() => setIdx(Math.max(0, idx - 1))} className="p-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer transition-colors">
                <ChevronLeft size={16} />
              </button>
              <input type="range" min={0} max={keyframes.length - 1} value={idx}
                onChange={e => setIdx(parseInt(e.target.value))} className="flex-1" />
              <button onClick={() => setIdx(Math.min(keyframes.length - 1, idx + 1))} className="p-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg-card)] text-[var(--color-text-muted)] hover:text-[var(--color-text-primary)] cursor-pointer transition-colors">
                <ChevronRight size={16} />
              </button>
              <span className="text-xs text-[var(--color-text-muted)] tabular-nums">{idx + 1}/{keyframes.length}</span>
            </div>

            {/* Thumbnail Grid */}
            <div className="grid grid-cols-[repeat(auto-fill,minmax(80px,1fr))] gap-1.5">
              {keyframes.map((k, i) => (
                <img key={k.id} src={api.imageUrl(k.id)} alt=""
                  onClick={() => setIdx(i)}
                  className={`w-full aspect-video object-cover rounded-lg cursor-pointer border-2 transition-all ${
                    i === idx ? "border-[var(--color-accent)] shadow-md shadow-blue-500/10" : "border-transparent hover:border-[var(--color-border)]"
                  }`} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
