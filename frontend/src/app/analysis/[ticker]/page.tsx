"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AnalysisResult, StreamUpdate, SIGNAL_DISPLAY, GOING_CONCERN_STATUS, PatternMatch, SimilarCase } from "@/lib/types";
import { TimelineContext, SignalTimeline, SimilarCompanies, ProcessingStages } from "@/components";

type Stage = {
  name: string;
  status: "pending" | "processing" | "completed" | "error";
  message?: string;
};

const INITIAL_STAGES: Stage[] = [
  { name: "Fetching SEC filings", status: "pending" },
  { name: "Extracting signals", status: "pending" },
  { name: "Validating signals", status: "pending" },
  { name: "Syncing to timeline", status: "pending" },
  { name: "Generating report", status: "pending" },
];

export default function AnalysisPage() {
  const params = useParams();
  const ticker = (params.ticker as string)?.toUpperCase();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stages, setStages] = useState<Stage[]>(INITIAL_STAGES);
  const [signalsFound, setSignalsFound] = useState(0);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [similarCases, setSimilarCases] = useState<SimilarCase[]>([]);
  const jobIdRef = useRef<string | null>(null);
  const isCompletedRef = useRef(false);

  const updateStageFromMessage = useCallback((update: StreamUpdate) => {
    setSignalsFound(update.signals_found || 0);

    setStages((prev) => {
      const newStages = [...prev];
      const stageMap: Record<string, number> = {
        fetching: 0,
        extracting: 1,
        validating: 2,
        syncing: 3,
        reporting: 4,
      };

      const currentIndex = stageMap[update.stage] ?? -1;

      // Mark all previous stages as completed
      for (let i = 0; i < currentIndex; i++) {
        newStages[i] = { ...newStages[i], status: "completed" };
      }

      // Mark current stage as processing
      if (currentIndex >= 0 && currentIndex < newStages.length) {
        newStages[currentIndex] = {
          ...newStages[currentIndex],
          status: "processing",
          message: update.message,
        };
      }

      return newStages;
    });
  }, []);

  // Cancel analysis when leaving the page
  const cancelAnalysis = useCallback(async () => {
    if (jobIdRef.current && !isCompletedRef.current) {
      try {
        await api.cancelAnalysis(jobIdRef.current);
      } catch (e) {
        console.log("Cancel request failed (may have already completed):", e);
      }
    }
  }, []);

  useEffect(() => {
    if (!ticker) return;

    let cleanup: (() => void) | undefined;

    const startAnalysis = async () => {
      try {
        const response = await api.startAnalysis(ticker);
        jobIdRef.current = response.job_id;

        if (response.cached) {
          isCompletedRef.current = true;
          const cachedResult = await api.getJobStatus(response.job_id);
          if (cachedResult.result) {
            setResult(cachedResult.result);
            setStages((prev) => prev.map((s) => ({ ...s, status: "completed" as const })));
            setIsLoading(false);
            return;
          }
        }

        cleanup = api.subscribeToStream(
          response.job_id,
          (update) => {
            updateStageFromMessage(update);
          },
          (analysisResult) => {
            isCompletedRef.current = true;
            setResult(analysisResult);
            setStages((prev) => prev.map((s) => ({ ...s, status: "completed" as const })));
            setIsLoading(false);
          },
          (errorMsg) => {
            isCompletedRef.current = true;
            setError(errorMsg);
            setIsLoading(false);
          }
        );
      } catch (err) {
        isCompletedRef.current = true;
        setError(err instanceof Error ? err.message : "Failed to start analysis");
        setIsLoading(false);
      }
    };

    const handleBeforeUnload = () => {
      if (jobIdRef.current && !isCompletedRef.current) {
        navigator.sendBeacon(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/analyze/${jobIdRef.current}/cancel`
        );
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    startAnalysis();

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      if (cleanup) cleanup();
      cancelAnalysis();
    };
  }, [ticker, updateStageFromMessage, cancelAnalysis]);

  // Fetch similar cases from Neo4j when analysis completes
  useEffect(() => {
    if (result && ticker) {
      api.getSimilarCases(ticker)
        .then(setSimilarCases)
        .catch((err) => console.log("Could not fetch similar cases:", err));
    }
  }, [result, ticker]);

  if (error) {
    return (
      <main className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-4xl mx-auto px-4">
          <div className="bg-white rounded-xl shadow-lg p-8 text-center">
            <div className="text-red-500 text-5xl mb-4">!</div>
            <h1 className="text-2xl font-bold mb-2">Analysis Failed</h1>
            <p className="text-gray-600 mb-6">{error}</p>
            <Link
              href="/"
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Try Another Ticker
            </Link>
          </div>
        </div>
      </main>
    );
  }

  if (isLoading && !result) {
    return (
      <main className="min-h-screen bg-gray-50 py-12">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold mb-2">Analyzing {ticker}</h1>
            <p className="text-gray-600">This may take a few minutes...</p>
          </div>
          <ProcessingStages stages={stages} signalsFound={signalsFound} />
        </div>
      </main>
    );
  }

  if (!result) {
    return null;
  }

  const gcStatus = result.going_concern_status || "NEVER";
  const gcDisplay = GOING_CONCERN_STATUS[gcStatus] || GOING_CONCERN_STATUS.NEVER;

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="border-b bg-white sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-blue-600">
            SEC Insights
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              New Analysis
            </Link>
          </div>
        </div>
      </nav>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <h1 className="text-3xl font-bold">{result.ticker}</h1>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${gcDisplay.color}`}
                >
                  GC: {gcDisplay.label}
                </span>
              </div>
              <p className="text-xl text-gray-600">{result.company_name}</p>
              <p className="text-sm text-gray-400 mt-1">CIK: {result.cik}</p>
            </div>
            <TimelineContext
              goingConcernStatus={gcStatus}
              goingConcernFirstSeen={result.going_concern_first_seen}
              goingConcernLastSeen={result.going_concern_last_seen}
              firstSignalDate={result.first_signal_date}
              lastSignalDate={result.last_signal_date}
              daysSinceLastSignal={result.days_since_last_signal}
              signalCount={result.signal_count}
              size="medium"
            />
          </div>
        </div>

        {/* Going Concern Alert */}
        {gcStatus === "ACTIVE" && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-bold text-red-800 mb-1">Active Going Concern Warning</h3>
                <p className="text-red-700">
                  This company has an active going concern warning in its SEC filings.
                  {result.going_concern_first_seen && (
                    <> First detected: {new Date(result.going_concern_first_seen).toLocaleDateString()}.</>
                  )}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Going Concern Removed - Positive Signal */}
        {gcStatus === "REMOVED" && (
          <div className="bg-green-50 border border-green-200 rounded-xl p-6 mb-6">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <h3 className="text-lg font-bold text-green-800 mb-1">Going Concern Removed</h3>
                <p className="text-green-700">
                  Going concern warning was removed in the latest annual filing - a positive development.
                  {result.going_concern_last_seen && (
                    <> Last seen: {new Date(result.going_concern_last_seen).toLocaleDateString()}.</>
                  )}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Historical Pattern Match (kept as informational, not predictive) */}
        {result.bankruptcy_pattern_match && (
          <HistoricalPatternCard match={result.bankruptcy_pattern_match} />
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Signal Summary */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">
                Detected Signals ({result.signal_count})
              </h2>
              {result.signal_count === 0 ? (
                <p className="text-gray-500">No distress signals detected in analyzed filings.</p>
              ) : (
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {Object.entries(result.signal_summary).map(([type, count]) => {
                    const display = SIGNAL_DISPLAY[type] || { label: type, color: "gray" };
                    return (
                      <div
                        key={type}
                        className={`p-3 rounded-lg border ${
                          display.color === "red"
                            ? "bg-red-50 border-red-200"
                            : display.color === "orange"
                            ? "bg-orange-50 border-orange-200"
                            : display.color === "yellow"
                            ? "bg-yellow-50 border-yellow-200"
                            : "bg-gray-50 border-gray-200"
                        }`}
                      >
                        <div className="font-semibold text-lg">{count}</div>
                        <div className="text-sm text-gray-600">{display.label}</div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Timeline */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">Signal Timeline</h2>
              {result.timeline.length > 0 ? (
                <SignalTimeline events={result.timeline} />
              ) : (
                <p className="text-gray-500">No timeline events to display.</p>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Similar Companies (historical comparison only) */}
            {similarCases && similarCases.length > 0 && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-xl font-bold mb-4">Similar Historical Cases</h2>
                <p className="text-sm text-gray-500 mb-4">
                  Companies with overlapping signal patterns (for reference only)
                </p>
                <div className="space-y-3">
                  {similarCases.map((company, index) => (
                    <Link
                      key={index}
                      href={`/analysis/${company.ticker}`}
                      className="block bg-gray-50 rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-lg">{company.ticker}</span>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            company.outcome === "BANKRUPT" ? "bg-red-100 text-red-800" : "bg-gray-100 text-gray-800"
                          }`}>
                            {company.outcome}
                          </span>
                        </div>
                      </div>
                      <div className="text-sm text-gray-600 mb-2">{company.name}</div>
                      <div className="text-sm text-gray-500 mb-2">
                        {company.overlap_count} overlapping signals
                      </div>
                      {company.matching_signals && company.matching_signals.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {company.matching_signals.slice(0, 3).map((type, i) => (
                            <span key={i} className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
                              {type.replace(/_/g, " ")}
                            </span>
                          ))}
                          {company.matching_signals.length > 3 && (
                            <span className="px-2 py-0.5 bg-gray-200 text-gray-600 text-xs rounded">
                              +{company.matching_signals.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </Link>
                  ))}
                </div>
              </div>
            )}

            {/* Analysis Metadata */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">Analysis Details</h2>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Filings Analyzed</span>
                  <span className="font-medium">{result.filings_analyzed}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Signals Extracted</span>
                  <span className="font-medium">{result.validation?.total_extracted || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Signals Validated</span>
                  <span className="font-medium">{result.validation?.total_validated || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Validation Rate</span>
                  <span className="font-medium">
                    {Math.round((result.validation?.validation_rate || 0) * 100)}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Analyzed At</span>
                  <span className="font-medium">
                    {new Date(result.analyzed_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <h3 className="font-semibold text-blue-800 mb-2">About This Analysis</h3>
              <p className="text-xs text-blue-700">
                This analysis presents factual information extracted from SEC filings.
                We do not provide risk scores, predictions, or investment advice.
                All signals are sourced directly from public SEC filings.
                You should interpret this data yourself and consult with qualified
                professionals before making any decisions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function HistoricalPatternCard({ match }: { match: PatternMatch }) {
  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 mb-6">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center">
          <svg className="w-6 h-6 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
        </div>
        <div className="flex-grow">
          <h3 className="text-lg font-bold text-gray-800 mb-1">Historical Pattern Reference</h3>
          <p className="text-gray-600 mb-3">
            Signal pattern has {Math.round(match.similarity_score * 100)}% overlap with
            {" "}{match.company_name} ({match.matched_company}), which filed for bankruptcy
            on {match.bankruptcy_date}.
          </p>
          <p className="text-xs text-gray-500 mb-3">
            This is historical data for reference only - not a prediction.
          </p>
          <div className="flex flex-wrap gap-2">
            {match.matching_signals.map((signal, i) => (
              <span key={i} className="px-2 py-1 bg-gray-200 text-gray-700 text-sm rounded">
                {signal.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
