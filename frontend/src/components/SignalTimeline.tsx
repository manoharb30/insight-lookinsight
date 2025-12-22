"use client";

import { TimelineEvent, SIGNAL_DISPLAY } from "@/lib/types";

interface SignalTimelineProps {
  events: TimelineEvent[];
}

export function SignalTimeline({ events }: SignalTimelineProps) {
  if (!events || events.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        No signals detected in the analysis period.
      </div>
    );
  }

  const getColorClass = (type: string) => {
    const display = SIGNAL_DISPLAY[type];
    if (!display) return "border-gray-400 bg-gray-100";

    switch (display.color) {
      case "red": return "border-red-500 bg-red-100";
      case "orange": return "border-orange-500 bg-orange-100";
      case "yellow": return "border-yellow-500 bg-yellow-100";
      default: return "border-gray-400 bg-gray-100";
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />

      <div className="space-y-4">
        {events.map((event, index) => {
          const display = SIGNAL_DISPLAY[event.type] || { label: event.type.replace(/_/g, " "), color: "gray" };

          return (
            <div key={index} className="relative pl-10">
              {/* Timeline dot */}
              <div className={`absolute left-2 w-4 h-4 rounded-full border-2 ${getColorClass(event.type)}`} />

              <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex items-start justify-between mb-2">
                  <span className={`px-2 py-1 rounded text-sm font-medium ${
                    display.color === "red" ? "bg-red-100 text-red-800" :
                    display.color === "orange" ? "bg-orange-100 text-orange-800" :
                    display.color === "yellow" ? "bg-yellow-100 text-yellow-800" :
                    "bg-gray-100 text-gray-800"
                  }`}>
                    {display.label}
                  </span>
                  <span className="text-sm text-gray-500">{formatDate(event.date)}</span>
                </div>

                <p className="text-sm text-gray-700 line-clamp-2">{event.evidence}</p>

                <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                  <span>Severity: {event.severity}/10</span>
                  <span>{event.filing_type}</span>
                  <span>Item {event.item_number}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
