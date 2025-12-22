"use client";

interface RiskGaugeProps {
  score: number;
  level: string;
  size?: "small" | "medium" | "large";
}

export function RiskGauge({ score, level, size = "medium" }: RiskGaugeProps) {
  const getColor = (score: number) => {
    if (score >= 70) return { ring: "text-red-500", bg: "bg-red-100", text: "text-red-700" };
    if (score >= 50) return { ring: "text-orange-500", bg: "bg-orange-100", text: "text-orange-700" };
    if (score >= 30) return { ring: "text-yellow-500", bg: "bg-yellow-100", text: "text-yellow-700" };
    return { ring: "text-green-500", bg: "bg-green-100", text: "text-green-700" };
  };

  const colors = getColor(score);
  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  const sizes = {
    small: { container: "w-24 h-24", text: "text-xl", label: "text-xs" },
    medium: { container: "w-40 h-40", text: "text-4xl", label: "text-sm" },
    large: { container: "w-56 h-56", text: "text-6xl", label: "text-base" },
  };

  const sizeClasses = sizes[size];

  return (
    <div className={`relative ${sizeClasses.container}`}>
      {/* Background circle */}
      <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          className="text-gray-200"
        />
        {/* Progress circle */}
        <circle
          cx="50"
          cy="50"
          r="45"
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeLinecap="round"
          className={colors.ring}
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: strokeDashoffset,
            transition: "stroke-dashoffset 1s ease-in-out",
          }}
        />
      </svg>
      {/* Center text */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`font-bold ${sizeClasses.text} ${colors.text}`}>{score}</span>
        <span className={`${sizeClasses.label} font-medium ${colors.text} ${colors.bg} px-2 py-0.5 rounded`}>
          {level}
        </span>
      </div>
    </div>
  );
}
