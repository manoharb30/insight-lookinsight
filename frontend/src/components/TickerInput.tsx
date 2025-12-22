"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";

interface TickerInputProps {
  size?: "default" | "large";
  placeholder?: string;
}

export function TickerInput({ size = "default", placeholder = "Enter ticker (e.g., PLUG, TSLA)" }: TickerInputProps) {
  const [ticker, setTicker] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;

    setIsLoading(true);
    router.push(`/analysis/${ticker.toUpperCase()}`);
  };

  const inputClasses = size === "large"
    ? "w-full px-6 py-4 text-xl border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all uppercase"
    : "w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all uppercase";

  const buttonClasses = size === "large"
    ? "px-8 py-4 text-xl font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-all"
    : "px-6 py-3 text-lg font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-all";

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 w-full max-w-xl">
      <input
        type="text"
        value={ticker}
        onChange={(e) => setTicker(e.target.value.toUpperCase())}
        placeholder={placeholder}
        className={inputClasses}
        maxLength={5}
        disabled={isLoading}
      />
      <button type="submit" className={buttonClasses} disabled={isLoading || !ticker.trim()}>
        {isLoading ? (
          <span className="flex items-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Analyzing...
          </span>
        ) : (
          "Analyze"
        )}
      </button>
    </form>
  );
}
