"use client";

import { SimilarCompany, GOING_CONCERN_STATUS } from "@/lib/types";
import Link from "next/link";

interface SimilarCompaniesProps {
  companies: SimilarCompany[];
}

export function SimilarCompanies({ companies }: SimilarCompaniesProps) {
  if (!companies || companies.length === 0) {
    return (
      <div className="text-center py-4 text-gray-500">
        No similar companies found in the database.
      </div>
    );
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "BANKRUPT":
        return "bg-red-100 text-red-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const getGCBadge = (gcStatus: string | undefined) => {
    if (!gcStatus) return null;
    const display = GOING_CONCERN_STATUS[gcStatus];
    if (!display) return null;
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${display.color}`}>
        GC: {display.label}
      </span>
    );
  };

  return (
    <div className="space-y-3">
      {companies.map((company, index) => (
        <Link
          key={index}
          href={`/analysis/${company.ticker}`}
          className="block bg-white rounded-lg border border-gray-200 p-4 hover:shadow-md transition-shadow"
        >
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg">{company.ticker}</span>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${getStatusBadge(company.status)}`}>
                {company.status}
              </span>
              {getGCBadge(company.going_concern_status)}
            </div>
          </div>

          <div className="text-sm text-gray-600 mb-2">{company.name}</div>

          <div className="flex items-center justify-between text-sm">
            <div className="text-gray-500">
              {company.common_signals} overlapping signals
            </div>
            <div className="text-blue-600 font-medium">
              {Math.round(company.similarity_score * 100)}% overlap
            </div>
          </div>

          {company.common_signal_types && company.common_signal_types.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {company.common_signal_types.slice(0, 3).map((type, i) => (
                <span key={i} className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                  {type.replace(/_/g, " ")}
                </span>
              ))}
              {company.common_signal_types.length > 3 && (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded">
                  +{company.common_signal_types.length - 3} more
                </span>
              )}
            </div>
          )}
        </Link>
      ))}
    </div>
  );
}
