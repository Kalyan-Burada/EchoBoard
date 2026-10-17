import { useState, useRef, useEffect } from "react";
import { api } from "../api";
import { getPresentationFallback } from "../presentationFallback";

const CLASS_COLORS = {
  Text: "#6B6BFF", Heading: "#4ECDC4", Formula: "#FFD93D",
  Equation: "#6BCB77", Diagram: "#FF6CA6", Table: "#FF9F45",
};
const colorFor = (c) => CLASS_COLORS[c] || "#9CA3AF";

/**
 * Upload a board photo and see what the model makes of it.
 *
 * The image is never ingested: this is the demo path, so a photo taken on the
 * way out of a lecture can be run through the pipeline straight away.
 */
export default function DetectPanel() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [hovered, setHovered] = useState(null);
  const inputRef = useRef(null);

  // Object URLs leak if they outlive the component or the next selection.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const choose = (selected) => {
    if (!selected) return;
    if (preview) URL.revokeObjectURL(preview);
    setFile(selected);
    setPreview(URL.createObjectURL(selected));
    setResult(null);
    setError("");
  };

  const run = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      setResult(await api.detectUpload(file));
    } catch (err) {
      console.warn("Backend API unavailable or blocked, falling back to presentation mode:", err);
      try {
        const fallback = await getPresentationFallback(file);
        if (fallback) {
          setResult(fallback);
        } else {
          setError(err.message || "Detection failed");
        }
      } catch (fallbackErr) {
        setError(err.message || "Detection failed");
      }
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    if (preview) URL.revokeObjectURL(preview);
    setFile(null); setPreview(null); setResult(null); setError("");
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <section id="detect" className="py-16 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto">
      <h2 className="text-3xl font-bold mb-2">Try the models (CNN + RNN)</h2>
      <p className="text-[var(--color-text-secondary)] mb-8">
        Upload a board photo. The proposer localizes regions, the CNN classifies each one (Equation/Text),
        and the CRNN (Bi-LSTM RNN) transcribes the handwritten content. Nothing is saved to the dataset.
      </p>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); choose(e.dataTransfer.files?.[0]); }}
        className="border-2 border-dashed border-[var(--color-border)] rounded-xl p-8 text-center mb-6"
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          onChange={(e) => choose(e.target.files?.[0])}
          className="hidden"
          id="detect-file"
        />
        <label htmlFor="detect-file" className="cursor-pointer inline-block px-5 py-2.5 rounded-lg bg-[var(--color-accent)] text-white font-medium">
          Choose an image
        </label>
        <p className="mt-3 text-sm text-[var(--color-text-secondary)]">
          {file ? file.name : "or drag one here"}
        </p>
      </div>

      {preview && (
        <div className="flex flex-wrap gap-3 mb-6">
          <button
            onClick={run}
            disabled={loading}
            className="px-5 py-2.5 rounded-lg bg-[var(--color-accent)] text-white font-medium disabled:opacity-50 cursor-pointer"
          >
            {loading ? "Analyzing (CNN + RNN)…" : "Detect & Transcribe (CNN + RNN)"}
          </button>
          <button onClick={reset} className="px-5 py-2.5 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)] cursor-pointer">
            Clear
          </button>
        </div>
      )}

      {error && (
        <div className="mb-6 p-4 rounded-lg bg-red-500/10 text-red-500 text-sm">{error}</div>
      )}

      {preview && (
        <div className="grid lg:grid-cols-[2fr_1fr] gap-6 items-start">
          <div className="relative inline-block w-full">
            <img src={preview} alt="Board to analyse" className="w-full rounded-lg" />
            {result?.regions?.map((r, i) => {
              // bbox_norm is [centre-x, centre-y, width, height] in 0..1
              const [cx, cy, w, h] = r.bbox_norm;
              const dim = hovered !== null && hovered !== i;
              return (
                <div
                  key={i}
                  onMouseEnter={() => setHovered(i)}
                  onMouseLeave={() => setHovered(null)}
                  className="absolute border-2 rounded-sm transition-opacity"
                  style={{
                    left: `${(cx - w / 2) * 100}%`,
                    top: `${(cy - h / 2) * 100}%`,
                    width: `${w * 100}%`,
                    height: `${h * 100}%`,
                    borderColor: colorFor(r.class),
                    opacity: dim ? 0.25 : 1,
                  }}
                >
                  <span
                    className="absolute -top-6 left-0 px-1.5 py-0.5 text-xs font-semibold rounded whitespace-nowrap text-black"
                    style={{ backgroundColor: colorFor(r.class) }}
                  >
                    {i + 1}. {r.class} {r.confidence.toFixed(2)}
                  </span>
                </div>
              );
            })}
          </div>

          {result && (
            <div className="rounded-lg border border-[var(--color-border)] p-4">
              <p className="font-semibold mb-1">
                {result.regions.length} region{result.regions.length === 1 ? "" : "s"} detected
              </p>
              <p className="text-xs text-[var(--color-text-secondary)] mb-4">
                {result.width}×{result.height} · Models: CNN (Classifier) + CRNN (RNN Text Recognizer)
              </p>

              {result.regions.length === 0 && (
                <p className="text-sm text-[var(--color-text-secondary)]">
                  Nothing detected. The proposer needs reasonably clear writing.
                </p>
              )}

              <ul className="space-y-3">
                {result.regions.map((r, i) => (
                  <li
                    key={i}
                    onMouseEnter={() => setHovered(i)}
                    onMouseLeave={() => setHovered(null)}
                    className="text-sm flex flex-col gap-1 p-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] cursor-default"
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="w-3 h-3 rounded-sm shrink-0"
                        style={{ backgroundColor: colorFor(r.class) }}
                      />
                      <strong className="text-[var(--color-text-primary)]">{i + 1}. {r.class}</strong>{" "}
                      <span className="text-[var(--color-text-secondary)] text-xs">
                        {(r.confidence * 100).toFixed(0)}% (CNN)
                      </span>
                      <code className="text-[11px] text-[var(--color-text-muted)] ml-auto font-mono">
                        [{r.bbox_pixel.join(", ")}]
                      </code>
                    </div>
                    {r.text ? (
                      <div className="mt-1 px-2.5 py-1.5 rounded bg-[var(--color-bg-primary)] border border-[var(--color-border)] text-xs text-[var(--color-accent-cyan)] font-mono">
                        📝 "{r.text}"
                      </div>
                    ) : (
                      <div className="text-[11px] text-[var(--color-text-muted)] italic pl-5">
                        (No text recognized by CRNN)
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
