// API Client for SEC Insights Backend

import { AnalyzeResponse, JobStatus, AnalysisResult, StreamUpdate } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class APIClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async fetch<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Unknown error" }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Start a new analysis for a ticker
   */
  async startAnalysis(ticker: string): Promise<AnalyzeResponse> {
    return this.fetch<AnalyzeResponse>("/api/v1/analyze", {
      method: "POST",
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    });
  }

  /**
   * Get the status of an analysis job
   */
  async getJobStatus(jobId: string): Promise<JobStatus> {
    return this.fetch<JobStatus>(`/api/v1/analyze/${jobId}`);
  }

  /**
   * Get cached analysis for a ticker (if exists)
   */
  async getCachedAnalysis(ticker: string): Promise<AnalysisResult | null> {
    try {
      return await this.fetch<AnalysisResult>(`/api/v1/company/${ticker.toUpperCase()}`);
    } catch {
      return null;
    }
  }

  /**
   * Subscribe to SSE stream for real-time updates
   */
  subscribeToStream(
    jobId: string,
    onUpdate: (update: StreamUpdate) => void,
    onComplete: (result: AnalysisResult) => void,
    onError: (error: string) => void,
    onCancelled?: () => void
  ): () => void {
    const eventSource = new EventSource(`${this.baseUrl}/api/v1/stream/${jobId}`);

    eventSource.addEventListener("update", (event) => {
      try {
        const data = JSON.parse(event.data) as StreamUpdate;
        onUpdate(data);
      } catch (e) {
        console.error("Failed to parse update:", e);
      }
    });

    eventSource.addEventListener("complete", (event) => {
      try {
        const data = JSON.parse(event.data) as AnalysisResult;
        onComplete(data);
        eventSource.close();
      } catch (e) {
        console.error("Failed to parse complete:", e);
        onError("Failed to parse analysis result");
        eventSource.close();
      }
    });

    eventSource.addEventListener("cancelled", (event) => {
      console.log("Analysis was cancelled:", event.data);
      if (onCancelled) {
        onCancelled();
      } else {
        onError("Analysis was cancelled");
      }
      eventSource.close();
    });

    eventSource.addEventListener("error", (event: MessageEvent) => {
      try {
        // Parse the error message from the backend
        const data = JSON.parse(event.data);
        console.warn("SSE error (handled):", data.error);
        onError(data.error || "Analysis failed");
      } catch {
        // If we can't parse, it's likely a connection error
        console.warn("SSE connection error (handled)");
        onError("Connection error - please try again");
      }
      eventSource.close();
    });

    eventSource.onerror = () => {
      eventSource.close();
    };

    // Return cleanup function
    return () => {
      eventSource.close();
    };
  }

  /**
   * Get similar companies
   */
  async getSimilarCompanies(ticker: string): Promise<AnalysisResult["similar_companies"]> {
    return this.fetch(`/api/v1/similar/${ticker.toUpperCase()}`);
  }

  /**
   * Compare two companies
   */
  async compareCompanies(
    ticker1: string,
    ticker2: string
  ): Promise<{ company1: AnalysisResult; company2: AnalysisResult }> {
    return this.fetch("/api/v1/compare", {
      method: "POST",
      body: JSON.stringify({
        ticker1: ticker1.toUpperCase(),
        ticker2: ticker2.toUpperCase(),
      }),
    });
  }

  /**
   * Cancel a running analysis job
   */
  async cancelAnalysis(jobId: string): Promise<{ job_id: string; cancelled: boolean; message: string }> {
    return this.fetch(`/api/v1/analyze/${jobId}/cancel`, {
      method: "POST",
    });
  }

  /**
   * Health check
   */
  async healthCheck(): Promise<{ status: string }> {
    return this.fetch("/health");
  }
}

// Export singleton instance
export const api = new APIClient();

// Export class for testing
export { APIClient };
