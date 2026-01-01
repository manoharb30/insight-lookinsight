"use client";

import { GOING_CONCERN_STATUS } from "@/lib/types";

interface TimelineContextProps {
  goingConcernStatus: "ACTIVE" | "REMOVED" | "NEVER";
  goingConcernFirstSeen: string | null;
  goingConcernLastSeen: string | null;
  firstSignalDate: string | null;
  lastSignalDate: string | null;
  daysSinceLastSignal: number | null;
  signalCount: number;
  size?: "small" | "medium" | "large";
}

export function TimelineContext({
  goingConcernStatus,
  goingConcernFirstSeen,
  goingConcernLastSeen,
  firstSignalDate,
  lastSignalDate,
  daysSinceLastSignal,
  signalCount,
  size = "medium",
}: TimelineContextProps) {
  const gcDisplay = GOING_CONCERN_STATUS[goingConcernStatus] || GOING_CONCERN_STATUS.NEVER;

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A";
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

  const getDaysLabel = (days: number | null) => {
    if (days === null) return "N/A";
    if (days === 0) return "Today";
    if (days === 1) return "1 day ago";
    if (days < 30) return `${days} days ago`;
    if (days < 60) return "~1 month ago";
    if (days < 365) return `${Math.round(days / 30)} months ago`;
    return `${Math.round(days / 365)} year(s) ago`;
  };

  const sizes = {
    small: { container: "p-3", text: "text-sm", label: "text-xs" },
    medium: { container: "p-4", text: "text-base", label: "text-sm" },
    large: { container: "p-6", text: "text-lg", label: "text-base" },
  };

  const sizeClasses = sizes[size];

  return (
    <div className={`bg-white border rounded-xl ${sizeClasses.container}`}>
      {/* Going Concern Status */}
      <div className="mb-4">
        <div className={`${sizeClasses.label} text-gray-500 mb-1`}>Going Concern Status</div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-1 rounded-full ${sizeClasses.text} font-semibold ${gcDisplay.color}`}>
            {gcDisplay.label}
          </span>
        </div>
        <div className={`${sizeClasses.label} text-gray-500 mt-1`}>
          {gcDisplay.description}
        </div>
        {goingConcernStatus !== "NEVER" && (
          <div className={`${sizeClasses.label} text-gray-400 mt-1`}>
            {goingConcernStatus === "REMOVED" ? (
              <>
                First seen: {formatDate(goingConcernFirstSeen)}
                <br />
                Last seen: {formatDate(goingConcernLastSeen)}
              </>
            ) : (
              <>First seen: {formatDate(goingConcernFirstSeen)}</>
            )}
          </div>
        )}
      </div>

      {/* Timeline Summary */}
      <div className="border-t pt-4">
        <div className={`${sizeClasses.label} text-gray-500 mb-2`}>Signal Timeline</div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className={`${sizeClasses.text} font-bold text-gray-900`}>{signalCount}</div>
            <div className={`${sizeClasses.label} text-gray-500`}>Total Signals</div>
          </div>
          <div>
            <div className={`${sizeClasses.text} font-bold text-gray-900`}>
              {getDaysLabel(daysSinceLastSignal)}
            </div>
            <div className={`${sizeClasses.label} text-gray-500`}>Last Signal</div>
          </div>
        </div>
        {firstSignalDate && lastSignalDate && (
          <div className={`${sizeClasses.label} text-gray-400 mt-3`}>
            Range: {formatDate(firstSignalDate)} - {formatDate(lastSignalDate)}
          </div>
        )}
      </div>
    </div>
  );
}
