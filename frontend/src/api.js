export async function createReport(payload) {
  return requestJson("/api/v1/reports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getReport(reportId) {
  return requestJson(`/api/v1/reports/${encodeURIComponent(reportId)}`);
}

export async function listReports(filters) {
  const params = new URLSearchParams();
  if (filters.ticker) {
    params.set("ticker", filters.ticker);
  }
  if (filters.createdAfter) {
    params.set("createdAfter", filters.createdAfter);
  }
  if (filters.createdBefore) {
    params.set("createdBefore", filters.createdBefore);
  }

  const suffix = params.toString() ? `?${params}` : "";
  return requestJson(`/api/v1/reports${suffix}`);
}

export async function getCitation(reportId, evidenceId) {
  const params = new URLSearchParams({ evidenceId });
  return requestJson(`/api/v1/reports/${encodeURIComponent(reportId)}/citations?${params}`);
}

export function exportReportUrl(reportId, format) {
  return `/api/v1/reports/${encodeURIComponent(reportId)}/export?format=${encodeURIComponent(format)}`;
}

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("Content-Type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    throw new Error(body?.message || `HTTP ${response.status}`);
  }
  return body;
}
