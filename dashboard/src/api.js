const BASE = "http://localhost:8000";

export const api = {
  getStats: () => fetch(`${BASE}/api/stats`).then(r => r.json()),
  getVideos: () => fetch(`${BASE}/api/videos`).then(r => r.json()),
  getKeyframes: (videoId) => fetch(`${BASE}/api/videos/${videoId}/keyframes`).then(r => r.json()),
  deleteVideo: (videoId) => fetch(`${BASE}/api/videos/${videoId}`, { method: "DELETE" }).then(r => r.json()),
  stopVideo: (videoId) => fetch(`${BASE}/api/videos/${videoId}/stop`, { method: "POST" }).then(r => r.json()),
  imageUrl: (kfId) => `${BASE}/api/keyframes/${kfId}/image`,
  videoZipUrl: (videoId) => `${BASE}/api/videos/${videoId}/download`,
  datasetZipUrl: () => `${BASE}/api/download/dataset`,

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
};
