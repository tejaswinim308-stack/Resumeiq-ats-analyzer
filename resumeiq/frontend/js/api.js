/**
 * Thin wrapper around the ResumeIQ backend API. No secrets live here —
 * the Gemini key stays server-side. This file only knows the backend
 * base URL and the shape of its endpoints.
 */
const API = (() => {
  // Same-origin by default (works when frontend is served by Flask directly
  // or on Cloud Run; falls back to port 8080 if frontend is served on 5500).
  const BASE_URL = window.RESUMEIQ_API_BASE_URL || (
    typeof window !== "undefined" && window.location && window.location.origin && window.location.origin !== "null"
      ? (window.location.port === "5500" ? "http://localhost:8080" : window.location.origin)
      : "http://localhost:8080"
  );

  async function request(path, options = {}) {
    const headers = options.headers ? { ...options.headers } : {};
    if (options.token) {
      headers["Authorization"] = `Bearer ${options.token}`;
    }
    const fetchOptions = { ...options, headers };
    delete fetchOptions.token;

    let response;
    try {
      response = await fetch(`${BASE_URL}${path}`, fetchOptions);
    } catch (networkErr) {
      const err = new Error("Could not reach the ResumeIQ backend. Is it running?");
      err.code = "network_error";
      throw err;
    }

    let body = null;
    try {
      body = await response.json();
    } catch (_parseErr) {
      const err = new Error("The server returned an unreadable response.");
      err.code = "bad_response";
      throw err;
    }

    if (!response.ok || body.success === false) {
      const message = (body.error && body.error.message) || "Something went wrong.";
      const err = new Error(message);
      err.code = (body.error && body.error.code) || "unknown_error";
      throw err;
    }
    return body;
  }

  return {
    health() {
      return request("/api/health", { method: "GET" });
    },
    analyze(resumeFile, jobDescription, token = null) {
      const formData = new FormData();
      formData.append("resume", resumeFile);
      formData.append("job_description", jobDescription);
      return request("/api/analyze", { method: "POST", body: formData, token });
    },
    listHistory(token, limit = 25) {
      return request(`/api/history?limit=${limit}`, { method: "GET", token });
    },
    getHistory(analysisId, token) {
      return request(`/api/history/${encodeURIComponent(analysisId)}`, { method: "GET", token });
    },
    deleteHistory(analysisId, token) {
      return request(`/api/history/${encodeURIComponent(analysisId)}`, { method: "DELETE", token });
    },
    updateProfile(profileData, token) {
      return request("/api/auth/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileData),
        token,
      });
    },
  };
})();
