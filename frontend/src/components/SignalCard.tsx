"use client";

import { Signal, SIGNAL_DISPLAY } from "@/lib/types";

interface SignalCardProps {
  signal: Signal;
}

export function SignalCard({ signal }: SignalCardProps) {
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

  const getSeverityBadge = (severity: number) => {
    if (severity >= 8) return { text: "Critical", class: "bg-red-600 text-white" };
    if (severity >= 6) return { text: "High", class: "bg-orange-500 text-white" };
    if (severity >= 4) return { text: "Medium", class: "bg-yellow-500 text-white" };
    return { text: "Low", class: "bg-green-500 text-white" };
  };

  const severityBadge = getSeverityBadge(signal.severity);

  return (
    <div className={`p-4 rounded-lg border ${colorClasses.bg} ${colorClasses.border}`}>
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 rounded text-sm font-medium ${colorClasses.badge}`}>
            {display.label}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${severityBadge.class}`}>
            {severityBadge.text}
          </span>
        </div>
        <div className="text-right">
          <span className="text-sm text-gray-500">{signal.date}</span>
          <div className="text-xs text-gray-400">{signal.filing_type}</div>
        </div>
      </div>

      <p className="text-sm text-gray-700 mt-2 line-clamp-3">
        {signal.evidence}
      </p>

      <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
        <span>Confidence: {Math.round(signal.confidence * 100)}%</span>
        <span>Item {signal.item_number}</span>
      </div>
    </div>
  );
}
