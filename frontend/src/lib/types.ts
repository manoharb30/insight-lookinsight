// API Types for SEC Insights

export interface Signal {
  id: string;
  type: string;
  date: string;
  severity: number;
  confidence: number;
  evidence: string;
  filing_accession: string;
  filing_type: string;
  item_number: string;
  person?: string;
}

export interface TimelineEvent {
  date: string;
  type: string;
  severity: number;
  confidence: number;
  evidence: string;
  filing_type: string;
  item_number: string;
}

export interface RiskBreakdown {
  category: string;
  signals: number;
  contribution: number;
  percentage: number;
}

export interface SimilarCompany {
  ticker: string;
  name: string;
  status: string;
  risk_score: number;
  common_signals: number;
  common_signal_types: string[];
  similarity_score: number;
}

export interface PatternMatch {
  matched_company: string;
  company_name: string;
  bankruptcy_date: string;
  matching_signals: string[];
  match_count: number;
  similarity_score: number;
}

export interface ValidationStats {
  total_extracted: number;
  total_validated: number;
  total_rejected: number;
  validation_rate: number;
}

export interface AnalysisResult {
  ticker: string;
  cik: string;
  company_name: string;
  status: string;
  risk_score: number;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  signal_count: number;
  signal_summary: Record<string, number>;
  signals: Signal[];
  timeline: TimelineEvent[];
  risk_breakdown: RiskBreakdown[];
  similar_companies: SimilarCompany[];
  bankruptcy_pattern_match: PatternMatch | null;
  executive_summary: string;
  key_risks: string[];
  assessment_notes: string;
  validation: ValidationStats;
  filings_analyzed: number;
  analyzed_at: string;
  expires_at: string;
}

export interface JobStatus {
  job_id: string;
  status: "pending" | "processing" | "completed" | "failed";
  current_stage: string;
  message: string;
  progress: number;
  signals_found: number;
  result?: AnalysisResult;
  error?: string;
}

export interface StreamUpdate {
  stage: string;
  message: string;
  progress: number;
  signals_found: number;
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
  cached?: boolean;
}

// Signal type display names and colors
export const SIGNAL_DISPLAY: Record<string, { label: string; color: string; icon: string }> = {
  GOING_CONCERN: { label: "Going Concern", color: "red", icon: "AlertTriangle" },
  DEBT_DEFAULT: { label: "Debt Default", color: "red", icon: "DollarSign" },
  CEO_DEPARTURE: { label: "CEO Departure", color: "orange", icon: "UserMinus" },
  CFO_DEPARTURE: { label: "CFO Departure", color: "orange", icon: "UserMinus" },
  MASS_LAYOFFS: { label: "Mass Layoffs", color: "orange", icon: "Users" },
  COVENANT_VIOLATION: { label: "Covenant Violation", color: "red", icon: "FileWarning" },
  AUDITOR_CHANGE: { label: "Auditor Change", color: "yellow", icon: "FileText" },
  BOARD_RESIGNATION: { label: "Board Resignation", color: "yellow", icon: "UserX" },
  DELISTING_WARNING: { label: "Delisting Warning", color: "red", icon: "AlertOctagon" },
  CREDIT_DOWNGRADE: { label: "Credit Downgrade", color: "orange", icon: "TrendingDown" },
  ASSET_SALE: { label: "Asset Sale", color: "yellow", icon: "Package" },
  RESTRUCTURING: { label: "Restructuring", color: "orange", icon: "RefreshCw" },
  SEC_INVESTIGATION: { label: "SEC Investigation", color: "red", icon: "Search" },
  MATERIAL_WEAKNESS: { label: "Material Weakness", color: "yellow", icon: "Shield" },
  EQUITY_DILUTION: { label: "Equity Dilution", color: "yellow", icon: "Percent" },
};

// Risk level colors
export const RISK_COLORS: Record<string, string> = {
  LOW: "text-green-600 bg-green-100",
  MEDIUM: "text-yellow-600 bg-yellow-100",
  HIGH: "text-orange-600 bg-orange-100",
  CRITICAL: "text-red-600 bg-red-100",
};
