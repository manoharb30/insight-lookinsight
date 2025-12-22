import Link from "next/link";

export default function MethodologyPage() {
  return (
    <main className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="border-b bg-white">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/" className="text-xl font-bold text-blue-600">
            SEC Insights
          </Link>
          <div className="flex items-center gap-6">
            <Link href="/pricing" className="text-gray-600 hover:text-gray-900">
              Pricing
            </Link>
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              Analyze
            </Link>
          </div>
        </div>
      </nav>

      {/* Content */}
      <article className="max-w-4xl mx-auto px-4 py-16">
        <h1 className="text-4xl font-bold mb-8">How It Works</h1>

        <div className="prose prose-lg max-w-none">
          <section className="mb-12">
            <h2 className="text-2xl font-bold mb-4">Our Multi-Agent AI System</h2>
            <p className="text-gray-700 mb-4">
              SEC Insights uses a sophisticated multi-agent AI pipeline to analyze SEC filings and
              extract bankruptcy warning signals. Our system processes thousands of documents to
              identify patterns that have historically preceded corporate bankruptcies.
            </p>
          </section>

          <section className="mb-12">
            <h2 className="text-2xl font-bold mb-4">The Analysis Pipeline</h2>

            <div className="space-y-6">
              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-xl font-semibold mb-2 flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">
                    1
                  </span>
                  Filing Fetcher
                </h3>
                <p className="text-gray-600">
                  Our system retrieves SEC filings directly from the EDGAR database. We analyze 8-K
                  (current reports), 10-K (annual reports), and 10-Q (quarterly reports) from the
                  past 24 months.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-xl font-semibold mb-2 flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">
                    2
                  </span>
                  Signal Extractor
                </h3>
                <p className="text-gray-600">
                  Using GPT-4o, we extract specific bankruptcy warning signals from each filing. The
                  AI identifies 15+ signal types including going concern warnings, executive
                  departures, mass layoffs, and debt defaults.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-xl font-semibold mb-2 flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">
                    3
                  </span>
                  Signal Validator
                </h3>
                <p className="text-gray-600">
                  Every extracted signal is validated to eliminate false positives. We verify
                  evidence quotes, apply signal-specific rules, and assign confidence scores. Only
                  high-confidence signals are included in the final analysis.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-xl font-semibold mb-2 flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">
                    4
                  </span>
                  Risk Scorer
                </h3>
                <p className="text-gray-600">
                  Our pattern matching engine compares detected signals against known bankruptcy
                  cases (iRobot, WeWork, Bed Bath & Beyond, etc.). We calculate a weighted risk
                  score based on signal severity, recency, and pattern similarity.
                </p>
              </div>

              <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
                <h3 className="text-xl font-semibold mb-2 flex items-center gap-3">
                  <span className="w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm">
                    5
                  </span>
                  Report Generator
                </h3>
                <p className="text-gray-600">
                  Finally, we compile a comprehensive report with executive summary, signal
                  timeline, risk breakdown, and similar company comparisons.
                </p>
              </div>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-2xl font-bold mb-4">Signal Types We Detect</h2>

            <div className="grid md:grid-cols-2 gap-4">
              {[
                {
                  name: "Going Concern",
                  weight: 25,
                  desc: "Auditor doubt about company's ability to continue",
                },
                { name: "Debt Default", weight: 20, desc: "Missed payments or loan acceleration" },
                {
                  name: "Delisting Warning",
                  weight: 15,
                  desc: "Exchange compliance issues",
                },
                { name: "Mass Layoffs", weight: 15, desc: "Significant workforce reductions" },
                {
                  name: "Covenant Violation",
                  weight: 12,
                  desc: "Breach of loan agreement terms",
                },
                {
                  name: "CEO/CFO Departure",
                  weight: 10,
                  desc: "Executive resignations or terminations",
                },
                { name: "Credit Downgrade", weight: 10, desc: "Rating agency downgrades" },
                { name: "Restructuring", weight: 10, desc: "Formal restructuring plans" },
                { name: "Auditor Change", weight: 8, desc: "Change in independent auditor" },
                { name: "Asset Sale", weight: 8, desc: "Distressed asset divestitures" },
              ].map((signal, i) => (
                <div key={i} className="bg-white rounded-lg p-4 border border-gray-200">
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-semibold">{signal.name}</span>
                    <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                      Weight: {signal.weight}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600">{signal.desc}</p>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-2xl font-bold mb-4">Risk Score Calculation</h2>
            <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-200">
              <p className="text-gray-700 mb-4">
                The risk score (0-100) is calculated using a weighted formula that considers:
              </p>
              <ul className="list-disc list-inside space-y-2 text-gray-600">
                <li>
                  <strong>Base Weight:</strong> Each signal type has a base weight reflecting its
                  historical correlation with bankruptcy
                </li>
                <li>
                  <strong>Severity Multiplier:</strong> How severe the specific instance is (1-10
                  scale)
                </li>
                <li>
                  <strong>Recency Multiplier:</strong> Recent signals (last 6 months) are weighted
                  1.5x more heavily
                </li>
                <li>
                  <strong>Pattern Bonus:</strong> Additional points if the signal pattern matches a
                  known bankruptcy case
                </li>
              </ul>
            </div>
          </section>

          <section className="mb-12">
            <h2 className="text-2xl font-bold mb-4">Important Limitations</h2>
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
              <ul className="space-y-2 text-yellow-800">
                <li>• This tool is for informational purposes only</li>
                <li>• Past patterns do not guarantee future outcomes</li>
                <li>• Not all companies with warning signals will file for bankruptcy</li>
                <li>• Some bankruptcies may occur without detectable warning signals</li>
                <li>• Always consult with qualified financial advisors</li>
              </ul>
            </div>
          </section>
        </div>
      </article>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          &copy; {new Date().getFullYear()} SEC Insights. All rights reserved.
        </div>
      </footer>
    </main>
  );
}
