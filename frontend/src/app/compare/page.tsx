"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function ComparePage() {
  const [ticker1, setTicker1] = useState("");
  const [ticker2, setTicker2] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker1.trim() || !ticker2.trim()) return;

    setIsLoading(true);
    // For now, redirect to first ticker's analysis
    // In Phase 5, this would show a side-by-side comparison
    router.push(`/analysis/${ticker1.toUpperCase()}`);
  };

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-blue-600">
            SEC Insights
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/methodology" className="text-gray-600 hover:text-gray-900">
              Methodology
            </Link>
            <Link href="/pricing" className="text-gray-600 hover:text-gray-900">
              Pricing
            </Link>
          </div>
        </div>
      </nav>

      {/* Content */}
      <section className="max-w-4xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold mb-4">Compare Companies</h1>
          <p className="text-xl text-gray-600">
            Side-by-side comparison of bankruptcy risk signals
          </p>
        </div>

        <div className="bg-white rounded-xl shadow-lg p-8">
          <form onSubmit={handleCompare} className="space-y-6">
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Company 1
                </label>
                <input
                  type="text"
                  value={ticker1}
                  onChange={(e) => setTicker1(e.target.value.toUpperCase())}
                  placeholder="Enter ticker (e.g., PLUG)"
                  className="w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none uppercase"
                  maxLength={5}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Company 2
                </label>
                <input
                  type="text"
                  value={ticker2}
                  onChange={(e) => setTicker2(e.target.value.toUpperCase())}
                  placeholder="Enter ticker (e.g., TSLA)"
                  className="w-full px-4 py-3 text-lg border-2 border-gray-300 rounded-lg focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none uppercase"
                  maxLength={5}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading || !ticker1.trim() || !ticker2.trim()}
              className="w-full py-4 bg-blue-600 text-white text-lg font-semibold rounded-lg hover:bg-blue-700 disabled:bg-blue-400 disabled:cursor-not-allowed transition-colors"
            >
              {isLoading ? "Comparing..." : "Compare Companies"}
            </button>
          </form>

          <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-sm text-yellow-800">
              <strong>Pro Feature:</strong> Full side-by-side comparison is available with a Pro
              subscription. Free users can analyze one company at a time.
            </p>
          </div>
        </div>

        {/* Example Comparisons */}
        <div className="mt-12">
          <h2 className="text-2xl font-bold mb-6 text-center">Popular Comparisons</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              { t1: "IRBT", t2: "PTON", desc: "Both faced consumer electronics challenges" },
              { t1: "WEWORK", t2: "GME", desc: "High-profile distressed companies" },
              { t1: "PLUG", t2: "TSLA", desc: "EV and clean energy sector comparison" },
              { t1: "BBBYQ", t2: "SFIX", desc: "Retail sector distress patterns" },
            ].map((example, i) => (
              <button
                key={i}
                onClick={() => {
                  setTicker1(example.t1);
                  setTicker2(example.t2);
                }}
                className="text-left p-4 bg-white rounded-lg border border-gray-200 hover:border-blue-500 hover:shadow-md transition-all"
              >
                <div className="font-semibold">
                  {example.t1} vs {example.t2}
                </div>
                <div className="text-sm text-gray-600">{example.desc}</div>
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-8 mt-auto">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          &copy; {new Date().getFullYear()} SEC Insights. All rights reserved.
        </div>
      </footer>
    </main>
  );
}
