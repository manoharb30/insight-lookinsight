"use client";

import { TimelineEvent, SignalDetail, SIGNAL_DISPLAY } from "@/lib/types";

// Support both TimelineEvent (from analysis) and SignalDetail (from Neo4j timeline)
type TimelineItem = TimelineEvent | SignalDetail;

interface SignalTimelineProps {
  events: TimelineItem[];
  showDaysToNext?: boolean;
}

export function SignalTimeline({ events, showDaysToNext = true }: SignalTimelineProps) {
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

  const getDaysToNext = (event: TimelineItem): number | null => {
    if ('days_to_next' in event) {
      return event.days_to_next;
    }
    return null;
  };

  const getFilingType = (event: TimelineItem): string => {
    if ('filing' in event && event.filing) {
      return event.filing.type;
    }
    if ('filing_type' in event) {
      return event.filing_type;
    }
    return '';
  };

  const getItemNumber = (event: TimelineItem): string => {
    if ('filing' in event && event.filing) {
      return event.filing.item || '';
    }
    if ('item_number' in event) {
      return event.item_number;
    }
    return '';
  };

  return (
    <div className="relative">
      {/* Timeline line */}
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />

      <div className="space-y-4">
        {events.map((event, index) => {
          const display = SIGNAL_DISPLAY[event.type] || { label: event.type.replace(/_/g, " "), color: "gray" };
          const daysToNext = getDaysToNext(event);
          const filingType = getFilingType(event);
          const itemNumber = getItemNumber(event);

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
                  {filingType && <span>{filingType}</span>}
                  {itemNumber && <span>Item {itemNumber}</span>}
                </div>

                {/* Days to next signal indicator */}
                {showDaysToNext && daysToNext !== null && index < events.length - 1 && (
                  <div className="mt-3 flex items-center">
                    <div className="flex-1 h-px bg-gray-200" />
                    <span className={`mx-2 px-2 py-0.5 rounded-full text-xs font-medium ${
                      daysToNext <= 30 ? "bg-red-100 text-red-700" :
                      daysToNext <= 90 ? "bg-orange-100 text-orange-700" :
                      "bg-gray-100 text-gray-600"
                    }`}>
                      {daysToNext} days to next signal
                    </span>
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
