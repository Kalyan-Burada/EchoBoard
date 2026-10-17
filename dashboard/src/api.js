// Base URL of the EchoBoard backend API. Override per-machine via
// VITE_API_BASE in dashboard/.env.local or window localStorage.
export const getBaseUrl = () => {
  if (typeof window !== "undefined") {
    const override = localStorage.getItem("echoboard_api_base");
    if (override && override.trim()) return override.trim().replace(/\/+$/, "");
  }
  return (import.meta.env.VITE_API_BASE ?? "http://localhost:8000").replace(/\/+$/, "");
};

export const api = {
  // Dashboard stats
  getStats: () => fetch(`${getBaseUrl()}/api/stats`).then(r => r.json()),

  // Video management
  getVideos: () => fetch(`${getBaseUrl()}/api/videos`).then(r => r.json()),
  getKeyframes: (videoId) => fetch(`${getBaseUrl()}/api/videos/${videoId}/keyframes`).then(r => r.json()),
  deleteVideo: (videoId) => fetch(`${getBaseUrl()}/api/videos/${videoId}`, { method: "DELETE" }).then(r => r.json()),
  stopVideo: (videoId) => fetch(`${getBaseUrl()}/api/videos/${videoId}/stop`, { method: "POST" }).then(r => r.json()),

  // Image URLs
  imageUrl: (imageId) => `${getBaseUrl()}/api/keyframes/${imageId}/image`,
  rawImageUrl: (echdId) => `${getBaseUrl()}/api/dataset/images/${echdId}/raw`,

  // Download
  videoZipUrl: (videoId) => `${getBaseUrl()}/api/videos/${videoId}/download`,
  datasetZipUrl: () => `${getBaseUrl()}/api/download/dataset`,

  // Upload
  uploadVideo: (formData) =>
    fetch(`${getBaseUrl()}/api/upload/video`, { method: "POST", body: formData }).then(r => r.json()),

  uploadImages: (formData) =>
    fetch(`${getBaseUrl()}/api/upload/images`, { method: "POST", body: formData }).then(r => r.json()),

  uploadUrl: (payload) =>
    fetch(`${getBaseUrl()}/api/upload/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(r => r.json()),

  // Direct dataset upload (Stage 4)
  datasetUpload: (formData) =>
    fetch(`${getBaseUrl()}/dataset/upload`, { method: "POST", body: formData }).then(r => r.json()),

  // Dataset explorer
  getDatasetImages: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetch(`${getBaseUrl()}/api/dataset/images${qs ? "?" + qs : ""}`).then(r => r.json());
  },
  getDatasetImage: (imageId) => fetch(`${getBaseUrl()}/api/dataset/images/${imageId}`).then(r => r.json()),
  deleteDatasetImage: (imageId) => fetch(`${getBaseUrl()}/api/dataset/images/${imageId}`, { method: "DELETE" }).then(r => r.json()),
  runOcr: (imageId) => fetch(`${getBaseUrl()}/api/dataset/images/${imageId}/ocr`, { method: "POST" }).then(r => r.json()),

  // Region detection: proposed boxes + CNN class per region
  detectRegions: (imageId, persist = false) =>
    fetch(`${getBaseUrl()}/api/dataset/images/${imageId}/detect?persist=${persist}`, { method: "POST" })
      .then(async r => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail || "Detection failed");
        return body;
      }),
  // Run the pipeline on a brand-new image without ingesting it first
  detectUpload: (file) => {
    const form = new FormData();
    form.append("image", file);
    return fetch(`${getBaseUrl()}/api/detect/upload`, { method: "POST", body: form })
      .then(async r => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.detail || "Detection failed");
        return body;
      });
  },
  updateAnnotation: (imageId, text, annotationClass = "Text", reviewed = true) =>
    fetch(`${getBaseUrl()}/api/dataset/images/${imageId}/annotation`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ annotation_text: text, annotation_class: annotationClass, reviewed }),
    }).then(r => r.json()),

  // Dataset versions
  getVersions: () => fetch(`${getBaseUrl()}/api/dataset/versions`).then(r => r.json()),
  createVersion: (description) =>
    fetch(`${getBaseUrl()}/api/dataset/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    }).then(r => r.json()),
};
