"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AnalysisResult, StreamUpdate, SIGNAL_DISPLAY, PatternMatch } from "@/lib/types";
import { RiskGauge, SignalTimeline, SimilarCompanies, ProcessingStages } from "@/components";

type Stage = {
  name: string;
  status: "pending" | "processing" | "completed" | "error";
  message?: string;
};

const INITIAL_STAGES: Stage[] = [
  { name: "Fetching SEC filings", status: "pending" },
  { name: "Extracting signals", status: "pending" },
  { name: "Validating signals", status: "pending" },
  { name: "Calculating risk score", status: "pending" },
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

  const updateStageFromMessage = useCallback((update: StreamUpdate) => {
    setSignalsFound(update.signals_found || 0);

    setStages((prev) => {
      const newStages = [...prev];
      const stageMap: Record<string, number> = {
        fetching: 0,
        extracting: 1,
        validating: 2,
        scoring: 3,
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

  useEffect(() => {
    if (!ticker) return;

    const startAnalysis = async () => {
      try {
        // Start analysis
        const response = await api.startAnalysis(ticker);

        if (response.cached) {
          // Get cached result
          const cachedResult = await api.getJobStatus(response.job_id);
          if (cachedResult.result) {
            setResult(cachedResult.result);
            setStages((prev) => prev.map((s) => ({ ...s, status: "completed" as const })));
            setIsLoading(false);
            return;
          }
        }

        // Subscribe to SSE stream
        const cleanup = api.subscribeToStream(
          response.job_id,
          (update) => {
            updateStageFromMessage(update);
          },
          (analysisResult) => {
            setResult(analysisResult);
            setStages((prev) => prev.map((s) => ({ ...s, status: "completed" as const })));
            setIsLoading(false);
          },
          (errorMsg) => {
            setError(errorMsg);
            setIsLoading(false);
          }
        );

        return cleanup;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start analysis");
        setIsLoading(false);
      }
    };

    startAnalysis();
  }, [ticker, updateStageFromMessage]);

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
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    result.status === "BANKRUPT"
                      ? "bg-red-100 text-red-800"
                      : result.status === "DISTRESSED"
                      ? "bg-orange-100 text-orange-800"
                      : "bg-green-100 text-green-800"
                  }`}
                >
                  {result.status}
                </span>
              </div>
              <p className="text-xl text-gray-600">{result.company_name}</p>
              <p className="text-sm text-gray-400 mt-1">CIK: {result.cik}</p>
            </div>
            <RiskGauge score={result.risk_score} level={result.risk_level} size="large" />
          </div>
        </div>

        {/* Executive Summary */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4">Executive Summary</h2>
          <p className="text-gray-700 leading-relaxed">{result.executive_summary}</p>

          {result.key_risks && result.key_risks.length > 0 && (
            <div className="mt-4">
              <h3 className="font-semibold mb-2">Key Risk Factors:</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-600">
                {result.key_risks.map((risk, i) => (
                  <li key={i}>{risk}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Bankruptcy Pattern Match */}
        {result.bankruptcy_pattern_match && (
          <BankruptcyPatternCard match={result.bankruptcy_pattern_match} />
        )}

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Signal Summary */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">
                Signal Summary ({result.signal_count} signals)
              </h2>
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
            </div>

            {/* Timeline */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">Signal Timeline</h2>
              <SignalTimeline events={result.timeline} />
            </div>

            {/* Risk Breakdown */}
            {result.risk_breakdown && result.risk_breakdown.length > 0 && (
              <div className="bg-white rounded-xl shadow-lg p-6">
                <h2 className="text-xl font-bold mb-4">Risk Breakdown</h2>
                <div className="space-y-3">
                  {result.risk_breakdown.map((item, i) => (
                    <div key={i}>
                      <div className="flex justify-between mb-1">
                        <span className="font-medium">{item.category}</span>
                        <span className="text-gray-600">
                          {item.signals} signals ({item.percentage}%)
                        </span>
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-blue-600 rounded-full"
                          style={{ width: `${item.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Similar Companies */}
            <div className="bg-white rounded-xl shadow-lg p-6">
              <h2 className="text-xl font-bold mb-4">Similar Companies</h2>
              <SimilarCompanies companies={result.similar_companies} />
            </div>

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
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
              <h3 className="font-semibold text-yellow-800 mb-2">Disclaimer</h3>
              <p className="text-xs text-yellow-700">
                This analysis is for informational purposes only and does not constitute financial
                advice. Past patterns do not guarantee future outcomes. Always consult with a
                qualified financial advisor before making investment decisions.
              </p>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

function BankruptcyPatternCard({ match }: { match: PatternMatch }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-6">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
          <svg
            className="w-6 h-6 text-red-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <div className="flex-grow">
          <h3 className="text-lg font-bold text-red-800 mb-1">Bankruptcy Pattern Match</h3>
          <p className="text-red-700 mb-3">
            Signal pattern shows <strong>{Math.round(match.similarity_score * 100)}% similarity</strong>{" "}
            to {match.company_name} ({match.matched_company}) prior to its bankruptcy filing on{" "}
            {match.bankruptcy_date}.
          </p>
          <div className="flex flex-wrap gap-2">
            {match.matching_signals.map((signal, i) => (
              <span
                key={i}
                className="px-2 py-1 bg-red-100 text-red-800 text-sm rounded"
              >
                {signal.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
