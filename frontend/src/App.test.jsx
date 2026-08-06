import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.jsx";

const completedReport = {
  reportId: "report-test",
  status: "COMPLETED",
  tickers: ["NVDA"],
  reportType: "FILING_ANALYSIS",
  question: "Which filing discusses export controls?",
  timeHorizon: "30d",
  sourceFilters: ["SEC"],
  summary: "Generated report summary.",
  keyFindings: ["SEC evidence mentions export controls."],
  citations: [
    {
      evidenceId: "nvda-sec-risk-001#chunk-001",
      sourceType: "SEC",
      title: "NVDA sample filing risk factors",
      url: "https://example.com/nvda-sec-risk-001",
      section: "Risk Factors",
      sourceMetadata: { filing_date: "2026-05-28" },
    },
  ],
  sourceCoverage: { secChunks: 1, newsChunks: 0, earningsChunks: 0 },
  diagnostics: {
    mode: "local_retrieval",
    ragServiceStatus: "completed",
    retrievalStatus: "completed",
    generationStatus: "completed",
  },
  createdAt: "2026-08-05T10:00:00Z",
};

const citationDetail = {
  reportId: "report-test",
  evidenceId: "nvda-sec-risk-001#chunk-001",
  sourceType: "SEC",
  documentTitle: "NVDA sample filing risk factors",
  documentUrl: "https://example.com/nvda-sec-risk-001",
  section: "Risk Factors",
  publishedAt: "2026-05-28",
  sourceChunk: "Risk factors include export controls.",
  sourceMetadata: {
    filing_date: "2026-05-28",
    form_type: "10-Q",
  },
};

beforeEach(() => {
  global.fetch = vi.fn(async (url, options = {}) => {
    if (url === "/api/v1/reports" && options.method === "POST") {
      return jsonResponse(completedReport);
    }
    if (String(url).startsWith("/api/v1/reports/report-test/citations")) {
      return jsonResponse(citationDetail);
    }
    if (url === "/api/v1/reports/report-test") {
      return jsonResponse(completedReport);
    }
    if (String(url).startsWith("/api/v1/reports")) {
      return jsonResponse({ reports: [completedReport], count: 1 });
    }
    throw new Error(`Unexpected request: ${url}`);
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("App", () => {
  it("renders report history and opens citation details", async () => {
    render(<App />);

    expect(await screen.findByText("Financial RAG")).toBeInTheDocument();
    expect(await screen.findByText("NVDA sample filing risk factors")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Open" }));

    expect(await screen.findByText("Risk factors include export controls.")).toBeInTheDocument();
    expect(screen.getByText("10-Q")).toBeInTheDocument();
  });

  it("submits a report request to the backend API", async () => {
    render(<App />);

    await userEvent.clear(screen.getByLabelText("Tickers"));
    await userEvent.type(screen.getByLabelText("Tickers"), "nvda, amd");
    await userEvent.click(screen.getByRole("button", { name: "Generate Report" }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        "/api/v1/reports",
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("\"tickers\":[\"nvda\",\"amd\"]"),
        }),
      );
    });
    expect(await screen.findByText("Generated report summary.")).toBeInTheDocument();
  });
});

function jsonResponse(body) {
  return {
    ok: true,
    headers: new Headers({ "Content-Type": "application/json" }),
    json: async () => body,
  };
}
