const BASE = "http://localhost:8000";

export const api = {
  // Dashboard stats
  getStats: () => fetch(`${BASE}/api/stats`).then(r => r.json()),

  // Video management
  getVideos: () => fetch(`${BASE}/api/videos`).then(r => r.json()),
  getKeyframes: (videoId) => fetch(`${BASE}/api/videos/${videoId}/keyframes`).then(r => r.json()),
  deleteVideo: (videoId) => fetch(`${BASE}/api/videos/${videoId}`, { method: "DELETE" }).then(r => r.json()),
  stopVideo: (videoId) => fetch(`${BASE}/api/videos/${videoId}/stop`, { method: "POST" }).then(r => r.json()),

  // Image URLs
  imageUrl: (imageId) => `${BASE}/api/keyframes/${imageId}/image`,
  rawImageUrl: (echdId) => `${BASE}/api/dataset/images/${echdId}/raw`,

  // Download
  videoZipUrl: (videoId) => `${BASE}/api/videos/${videoId}/download`,
  datasetZipUrl: () => `${BASE}/api/download/dataset`,

  // Upload
  uploadVideo: (formData) =>
    fetch(`${BASE}/api/upload/video`, { method: "POST", body: formData }).then(r => r.json()),

  uploadImages: (formData) =>
    fetch(`${BASE}/api/upload/images`, { method: "POST", body: formData }).then(r => r.json()),

  uploadUrl: (payload) =>
    fetch(`${BASE}/api/upload/url`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(r => r.json()),

  // Direct dataset upload (Stage 4)
  datasetUpload: (formData) =>
    fetch(`${BASE}/dataset/upload`, { method: "POST", body: formData }).then(r => r.json()),

  // Dataset explorer
  getDatasetImages: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return fetch(`${BASE}/api/dataset/images${qs ? "?" + qs : ""}`).then(r => r.json());
  },
  getDatasetImage: (imageId) => fetch(`${BASE}/api/dataset/images/${imageId}`).then(r => r.json()),
  deleteDatasetImage: (imageId) => fetch(`${BASE}/api/dataset/images/${imageId}`, { method: "DELETE" }).then(r => r.json()),

  // Dataset versions
  getVersions: () => fetch(`${BASE}/api/dataset/versions`).then(r => r.json()),
  createVersion: (description) =>
    fetch(`${BASE}/api/dataset/versions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    }).then(r => r.json()),
};
