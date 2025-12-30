// API Types for SEC Insights - Facts Only, No Scores

export interface Signal {
  id: string;
  type: string;
  date: string;
  evidence: string;
  summary?: string;
  key_facts?: string[];
  filing_accession: string;
  filing_type: string;
  item_number: string;
  person?: string;
}

export interface TimelineEvent {
  date: string;
  type: string;
  evidence: string;
  filing_type: string;
  filing_accession: string;
  item_number: string;
}

export interface SimilarCompany {
  ticker: string;
  name: string;
  status: string;
  common_signals: number;
  common_signal_types: string[];
  similarity_score: number;
  going_concern_status?: string;
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
  signal_count: number;
  signal_summary: Record<string, number>;
  signals: Signal[];
  timeline: TimelineEvent[];

  // Going concern tracking (facts only)
  going_concern_status: "ACTIVE" | "REMOVED" | "NEVER";
  going_concern_first_seen: string | null;
  going_concern_last_seen: string | null;

  // Timeline context (facts only)
  first_signal_date: string | null;
  last_signal_date: string | null;
  days_since_last_signal: number | null;

  validation: ValidationStats;
  filings_analyzed: number;
  analyzed_at: string;
  expires_at: string;

  // Keep these for similar companies/historical comparison only
  similar_companies?: SimilarCompany[];
  bankruptcy_pattern_match?: PatternMatch | null;
}

// Neo4j Timeline API Types - Facts Only
export interface FilingInfo {
  type: string;
  item: string | null;
  date: string;
  url: string | null;
  accession: string;
}

export interface SignalDetail {
  id: string;
  type: string;
  date: string;
  evidence: string;
  fiscal_year: number | null;
  days_to_next: number | null;
  filing: FilingInfo | null;
}

export interface FilingDetail {
  accession: string;
  type: string;
  item: string | null;
  date: string;
  url: string | null;
  category: "DISTRESS" | "ROUTINE" | "CORPORATE_ACTION";
  summary: string | null;
}

export interface CompanyInfo {
  ticker: string;
  name: string;
  cik: string | null;
  status: string;
  bankruptcy_date: string | null;

  // Timeline context (no scores)
  first_signal_date: string | null;
  last_signal_date: string | null;
  days_since_last_signal: number | null;
  total_signals: number;

  // Going concern tracking
  going_concern_status: "ACTIVE" | "REMOVED" | "NEVER";
  going_concern_first_seen: string | null;
  going_concern_last_seen: string | null;
}

export interface CompanyTimeline {
  company: CompanyInfo;
  signals: SignalDetail[];
  recent_filings: FilingDetail[];
}

export interface GoingConcernYear {
  fiscal_year: number;
  has_going_concern: boolean;
  filing_date: string;
  url: string | null;
}

export interface GoingConcernHistory {
  ticker: string;
  years: GoingConcernYear[];
}

export interface SimilarCase {
  ticker: string;
  name: string;
  outcome: string;
  bankruptcy_date: string | null;
  going_concern_status: string | null;
  overlap_count: number;
  matching_signals: string[];
  timeline: { type: string; date: string }[];
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

// Going concern status display
export const GOING_CONCERN_STATUS: Record<string, { label: string; description: string; color: string }> = {
  ACTIVE: {
    label: "Active",
    description: "Going concern warning present in latest annual filing",
    color: "text-red-600 bg-red-100",
  },
  REMOVED: {
    label: "Removed",
    description: "Going concern was removed in latest annual filing (positive sign)",
    color: "text-green-600 bg-green-100",
  },
  NEVER: {
    label: "Never",
    description: "No going concern warnings detected in analyzed filings",
    color: "text-gray-600 bg-gray-100",
  },
};
