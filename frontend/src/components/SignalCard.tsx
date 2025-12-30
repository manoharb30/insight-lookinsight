"use client";

import { useState } from "react";
import { Signal, SIGNAL_DISPLAY } from "@/lib/types";

interface SignalCardProps {
  signal: Signal;
}

export function SignalCard({ signal }: SignalCardProps) {
  const [showModal, setShowModal] = useState(false);

  const display = SIGNAL_DISPLAY[signal.type] || {
    label: signal.type.replace(/_/g, " "),
    color: "gray",
    icon: "AlertCircle"
  };

  const getColorClasses = (color: string) => {
    const colors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
      red: { bg: "bg-red-50", border: "border-red-200", text: "text-red-800", badge: "bg-red-100 text-red-800" },
      orange: { bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-800", badge: "bg-orange-100 text-orange-800" },
      yellow: { bg: "bg-yellow-50", border: "border-yellow-200", text: "text-yellow-800", badge: "bg-yellow-100 text-yellow-800" },
      gray: { bg: "bg-gray-50", border: "border-gray-200", text: "text-gray-800", badge: "bg-gray-100 text-gray-800" },
    };
    return colors[color] || colors.gray;
  };

  const colorClasses = getColorClasses(display.color);

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <>
      <div className={`p-4 rounded-lg border ${colorClasses.bg} ${colorClasses.border}`}>
        <div className="flex items-start justify-between mb-2">
          <span className={`px-2 py-1 rounded text-sm font-medium ${colorClasses.badge}`}>
            {display.label}
          </span>
          <div className="text-right">
            <span className="text-sm text-gray-500">{formatDate(signal.date)}</span>
            <div className="text-xs text-gray-400">{signal.filing_type}</div>
          </div>
        </div>

        {/* Summary - main explanation */}
        {signal.summary && (
          <p className="text-sm text-gray-800 mt-2 font-medium">
            {signal.summary}
          </p>
        )}

        {/* Key Facts - bullet points */}
        {signal.key_facts && signal.key_facts.length > 0 && (
          <ul className="mt-2 space-y-1">
            {signal.key_facts.map((fact, idx) => (
              <li key={idx} className="text-sm text-gray-700 flex items-start">
                <span className="text-gray-400 mr-2">•</span>
                {fact}
              </li>
            ))}
          </ul>
        )}

        {/* Fallback to evidence if no summary */}
        {!signal.summary && (
          <p className="text-sm text-gray-700 mt-2 line-clamp-3">
            {signal.evidence}
          </p>
        )}

        <div className="flex items-center justify-between mt-3">
          <div className="flex items-center gap-4 text-xs text-gray-500">
            {signal.item_number && <span>Item {signal.item_number}</span>}
            {signal.filing_accession && (
              <span className="text-gray-400">
                Accession: {signal.filing_accession.slice(-10)}
              </span>
            )}
          </div>

          {/* Read More button */}
          <button
            onClick={() => setShowModal(true)}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            Read Filing Text →
          </button>
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg max-w-3xl w-full max-h-[80vh] overflow-hidden shadow-xl">
            {/* Modal Header */}
            <div className={`p-4 border-b ${colorClasses.bg}`}>
              <div className="flex items-start justify-between">
                <div>
                  <span className={`px-2 py-1 rounded text-sm font-medium ${colorClasses.badge}`}>
                    {display.label}
                  </span>
                  <p className="mt-2 text-sm text-gray-600">
                    {signal.filing_type} • Item {signal.item_number} • {formatDate(signal.date)}
                  </p>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
                >
                  ×
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto max-h-[60vh]">
              {/* Summary */}
              {signal.summary && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-1">Summary</h4>
                  <p className="text-sm text-gray-800">{signal.summary}</p>
                </div>
              )}

              {/* Key Facts */}
              {signal.key_facts && signal.key_facts.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-1">Key Facts</h4>
                  <ul className="space-y-1">
                    {signal.key_facts.map((fact, idx) => (
                      <li key={idx} className="text-sm text-gray-700 flex items-start">
                        <span className="text-gray-400 mr-2">•</span>
                        {fact}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Full Evidence */}
              <div>
                <h4 className="text-sm font-semibold text-gray-700 mb-1">Original Filing Text</h4>
                <div className="bg-gray-50 p-3 rounded border text-sm text-gray-700 whitespace-pre-wrap">
                  {signal.evidence}
                </div>
              </div>

              {/* Filing Link */}
              {signal.filing_accession && (
                <div className="mt-4 pt-4 border-t">
                  <a
                    href={`https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&filenum=${signal.filing_accession}&type=&dateb=&owner=include&count=40`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:text-blue-800"
                  >
                    View full filing on SEC EDGAR →
                  </a>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t bg-gray-50">
              <button
                onClick={() => setShowModal(false)}
                className="w-full py-2 px-4 bg-gray-200 hover:bg-gray-300 rounded text-sm font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
