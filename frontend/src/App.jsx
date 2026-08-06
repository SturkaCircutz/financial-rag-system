import { useEffect, useMemo, useState } from "react";

import { createReport, exportReportUrl, getCitation, getReport, listReports } from "./api.js";

const REPORT_TYPES = [
  ["COMPANY_BRIEF", "Company Brief"],
  ["EARNINGS_BRIEF", "Earnings Brief"],
  ["FILING_ANALYSIS", "Filing Analysis"],
  ["EVENT_DRIVEN", "Event Driven"],
  ["COMPARATIVE", "Comparative"],
];

const SOURCES = ["SEC", "NEWS", "EARNINGS"];

const emptyCitation = {
  sourceType: "None",
  documentTitle: "No citation selected",
  documentUrl: "",
  publishedAt: "",
  section: "",
  sourceChunk: "Select a citation.",
  sourceMetadata: {},
};

export default function App() {
  const [form, setForm] = useState({
    tickers: "NVDA",
    question: "What are the latest risk factors?",
    reportType: "COMPANY_BRIEF",
    timeHorizon: "30d",
    sourceFilters: SOURCES,
  });
  const [historyFilters, setHistoryFilters] = useState({ ticker: "", createdAfter: "", createdBefore: "" });
  const [history, setHistory] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [selectedCitation, setSelectedCitation] = useState(emptyCitation);
  const [status, setStatus] = useState("Ready");
  const [error, setError] = useState("");

  const exportDisabled = !selectedReport;
  const metadataEntries = useMemo(
    () => Object.entries(selectedCitation.sourceMetadata || {}).sort(([left], [right]) => left.localeCompare(right)),
    [selectedCitation],
  );

  useEffect(() => {
    refreshHistory();
  }, []);

  useEffect(() => {
    if (!selectedReport || !["QUEUED", "RUNNING"].includes(selectedReport.status)) {
      return undefined;
    }

    const timer = window.setInterval(async () => {
      try {
        const report = await getReport(selectedReport.reportId);
        setSelectedReport(report);
        if (["COMPLETED", "FAILED"].includes(report.status)) {
          window.clearInterval(timer);
          refreshHistory();
        }
      } catch (requestError) {
        setError(requestError.message);
        window.clearInterval(timer);
      }
    }, 900);

    return () => window.clearInterval(timer);
  }, [selectedReport?.reportId, selectedReport?.status]);

  async function refreshHistory(nextFilters = historyFilters) {
    try {
      const response = await listReports(normalizeHistoryFilters(nextFilters));
      const reports = response.reports || [];
      setHistory(reports);
      if (!selectedReport && reports.length > 0) {
        setSelectedReport(reports[0]);
      }
      setStatus("Ready");
    } catch (requestError) {
      setError(requestError.message);
      setStatus("Error");
    }
  }

  async function submitReport(event) {
    event.preventDefault();
    setError("");
    setStatus("Submitting");

    try {
      const report = await createReport({
        tickers: form.tickers.split(",").map((ticker) => ticker.trim()).filter(Boolean),
        question: form.question.trim(),
        reportType: form.reportType,
        timeHorizon: form.timeHorizon.trim(),
        sourceFilters: form.sourceFilters,
      });
      setSelectedReport(report);
      setSelectedCitation(emptyCitation);
      setStatus(report.status);
      refreshHistory();
    } catch (requestError) {
      setError(requestError.message);
      setStatus("Error");
    }
  }

  async function selectHistoryReport(reportId) {
    try {
      const report = await getReport(reportId);
      setSelectedReport(report);
      setSelectedCitation(emptyCitation);
      setStatus(report.status);
    } catch (requestError) {
      setError(requestError.message);
      setStatus("Error");
    }
  }

  async function openCitation(evidenceId) {
    if (!selectedReport) {
      return;
    }

    try {
      const citation = await getCitation(selectedReport.reportId, evidenceId);
      setSelectedCitation(citation);
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function updateSource(source) {
    setForm((current) => {
      const sources = current.sourceFilters.includes(source)
        ? current.sourceFilters.filter((candidate) => candidate !== source)
        : [...current.sourceFilters, source];
      return { ...current, sourceFilters: sources };
    });
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="compose-panel" aria-label="Create report">
          <div className="brand-row">
            <div>
              <h1>Financial RAG</h1>
              <p>Evidence-backed report workspace</p>
            </div>
            <span className="status-pill">{status}</span>
          </div>

          <form className="report-form" onSubmit={submitReport}>
            <label>
              <span>Tickers</span>
              <input
                value={form.tickers}
                onChange={(event) => setForm({ ...form, tickers: event.target.value })}
                autoComplete="off"
                placeholder="NVDA, AMD"
              />
            </label>

            <label>
              <span>Question</span>
              <textarea
                value={form.question}
                onChange={(event) => setForm({ ...form, question: event.target.value })}
                rows={4}
              />
            </label>

            <div className="form-grid">
              <label>
                <span>Report Type</span>
                <select value={form.reportType} onChange={(event) => setForm({ ...form, reportType: event.target.value })}>
                  {REPORT_TYPES.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>

              <label>
                <span>Time Horizon</span>
                <input
                  value={form.timeHorizon}
                  onChange={(event) => setForm({ ...form, timeHorizon: event.target.value })}
                />
              </label>
            </div>

            <fieldset>
              <legend>Sources</legend>
              {SOURCES.map((source) => (
                <label className="check-row" key={source}>
                  <input
                    type="checkbox"
                    checked={form.sourceFilters.includes(source)}
                    onChange={() => updateSource(source)}
                  />
                  {source}
                </label>
              ))}
            </fieldset>

            <button className="primary-action" type="submit">Generate Report</button>
            {error && <p className="error-message" role="alert">{error}</p>}
          </form>

          <section className="history-tools" aria-label="Report history filters">
            <div className="section-heading">
              <h2>History</h2>
              <button type="button" onClick={() => refreshHistory()}>Refresh</button>
            </div>

            <label>
              <span>Ticker Filter</span>
              <input
                value={historyFilters.ticker}
                onChange={(event) => setHistoryFilters({ ...historyFilters, ticker: event.target.value })}
                autoComplete="off"
                placeholder="NVDA"
              />
            </label>

            <div className="form-grid">
              <label>
                <span>After</span>
                <input
                  type="datetime-local"
                  value={historyFilters.createdAfter}
                  onChange={(event) => setHistoryFilters({ ...historyFilters, createdAfter: event.target.value })}
                />
              </label>
              <label>
                <span>Before</span>
                <input
                  type="datetime-local"
                  value={historyFilters.createdBefore}
                  onChange={(event) => setHistoryFilters({ ...historyFilters, createdBefore: event.target.value })}
                />
              </label>
            </div>

            <button type="button" onClick={() => refreshHistory()}>Apply Filters</button>
            <div className="history-list">
              {history.length === 0 ? (
                <p className="empty-state">No reports.</p>
              ) : history.map((report) => (
                <button
                  className="history-item"
                  key={report.reportId}
                  type="button"
                  onClick={() => selectHistoryReport(report.reportId)}
                >
                  <strong>{report.tickers.join(", ")}</strong>
                  <span className={`status-${report.status}`}>{report.status}</span>
                  <small>{report.reportType} · {formatDate(report.createdAt)}</small>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <section className="report-panel" aria-label="Report result">
          <div className="report-toolbar">
            <div>
              <p className="eyebrow">Selected Report</p>
              <h2>{selectedReport?.reportId || "No report selected"}</h2>
            </div>
            <div className="export-actions">
              {["markdown", "json", "pdf"].map((format) => (
                <a
                  aria-disabled={exportDisabled}
                  className={exportDisabled ? "disabled-link" : ""}
                  href={selectedReport ? exportReportUrl(selectedReport.reportId, format) : "#"}
                  key={format}
                >
                  {format.toUpperCase()}
                </a>
              ))}
            </div>
          </div>

          <div className="meta-grid">
            {selectedReport ? (
              [
                ["Status", selectedReport.status],
                ["Tickers", selectedReport.tickers.join(", ")],
                ["Type", selectedReport.reportType],
                ["Mode", selectedReport.diagnostics?.mode || "-"],
                ["Created", formatDate(selectedReport.createdAt)],
              ].map(([label, value]) => (
                <div className="meta-item" key={label}>
                  <span>{label}</span>
                  <strong className={label === "Status" ? `status-${value}` : ""}>{value}</strong>
                </div>
              ))
            ) : (
              <div className="meta-item">
                <span>Status</span>
                <strong>Waiting</strong>
              </div>
            )}
          </div>

          <article className="report-output">
            <section>
              <h3>Summary</h3>
              <p>{selectedReport?.summary || "Generate a report or select one from history."}</p>
            </section>

            <section>
              <h3>Key Findings</h3>
              <ul className="findings-list">
                {selectedReport?.keyFindings?.length
                  ? selectedReport.keyFindings.map((finding) => <li key={finding}>{finding}</li>)
                  : <li className="empty-state">No findings yet.</li>}
              </ul>
            </section>

            <section>
              <h3>Citations</h3>
              <div className="citation-list">
                {selectedReport?.citations?.length
                  ? selectedReport.citations.map((citation) => (
                    <div className="citation-card" key={citation.evidenceId}>
                      <div>
                        <strong>{citation.title || citation.evidenceId}</strong>
                        <span>{citation.sourceType} · {citation.section || "Unsectioned"}</span>
                      </div>
                      <button type="button" onClick={() => openCitation(citation.evidenceId)}>Open</button>
                    </div>
                  ))
                  : <p className="empty-state">No citations yet.</p>}
              </div>
            </section>
          </article>
        </section>

        <aside className="citation-panel" aria-label="Citation detail">
          <div className="section-heading">
            <h2>Citation</h2>
            <span className="source-chip">{selectedCitation.sourceType || "Source"}</span>
          </div>
          <dl className="citation-detail">
            <dt>Document</dt>
            <dd>{selectedCitation.documentTitle || selectedCitation.evidenceId}</dd>
            <dt>URL</dt>
            <dd>
              {selectedCitation.documentUrl
                ? <a href={selectedCitation.documentUrl} target="_blank" rel="noreferrer">{selectedCitation.documentUrl}</a>
                : "-"}
            </dd>
            <dt>Timestamp</dt>
            <dd>{selectedCitation.publishedAt || "-"}</dd>
            <dt>Section</dt>
            <dd>{selectedCitation.section || "-"}</dd>
          </dl>
          <pre className="source-chunk">{selectedCitation.sourceChunk || "No source chunk text was returned."}</pre>
          <div className="metadata-list">
            {metadataEntries.map(([key, value]) => (
              <div className="metadata-row" key={key}>
                <span>{key}</span>
                <span>{value}</span>
              </div>
            ))}
          </div>
        </aside>
      </section>
    </main>
  );
}

function normalizeHistoryFilters(filters) {
  return {
    ticker: filters.ticker.trim(),
    createdAfter: toIso(filters.createdAfter),
    createdBefore: toIso(filters.createdBefore),
  };
}

function toIso(value) {
  return value ? new Date(value).toISOString() : "";
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}
