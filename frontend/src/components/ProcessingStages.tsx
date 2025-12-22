"use client";

interface Stage {
  name: string;
  status: "pending" | "processing" | "completed" | "error";
  message?: string;
}

interface ProcessingStagesProps {
  stages: Stage[];
  signalsFound: number;
}

export function ProcessingStages({ stages, signalsFound }: ProcessingStagesProps) {
  const getStatusIcon = (status: Stage["status"]) => {
    switch (status) {
      case "completed":
        return (
          <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        );
      case "processing":
        return (
          <svg className="w-5 h-5 text-blue-500 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        );
      case "error":
        return (
          <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        );
      default:
        return (
          <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
        );
    }
  };

  const getStatusClass = (status: Stage["status"]) => {
    switch (status) {
      case "completed": return "text-green-700 bg-green-50";
      case "processing": return "text-blue-700 bg-blue-50";
      case "error": return "text-red-700 bg-red-50";
      default: return "text-gray-500 bg-gray-50";
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg p-6 max-w-lg mx-auto">
      <h2 className="text-xl font-semibold mb-6 text-center">Analyzing SEC Filings</h2>

      <div className="space-y-4">
        {stages.map((stage, index) => (
          <div key={index} className={`flex items-center gap-4 p-3 rounded-lg ${getStatusClass(stage.status)}`}>
            <div className="flex-shrink-0">
              {getStatusIcon(stage.status)}
            </div>
            <div className="flex-grow">
              <div className="font-medium">{stage.name}</div>
              {stage.message && (
                <div className="text-sm opacity-80">{stage.message}</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {signalsFound > 0 && (
        <div className="mt-6 text-center">
          <div className="text-3xl font-bold text-blue-600">{signalsFound}</div>
          <div className="text-sm text-gray-600">signals detected</div>
        </div>
      )}

      <div className="mt-6">
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-blue-600 transition-all duration-500"
            style={{
              width: `${(stages.filter(s => s.status === "completed").length / stages.length) * 100}%`
            }}
          />
        </div>
      </div>
    </div>
  );
}
