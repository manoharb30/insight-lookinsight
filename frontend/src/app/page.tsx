import { TickerInput } from "@/components";
import Link from "next/link";

// Featured analysis cards (pre-computed examples)
const FEATURED_ANALYSES = [
  { ticker: "IRBT", name: "iRobot Corp", status: "BANKRUPT", riskScore: 92, signals: 10 },
  { ticker: "WEWORK", name: "WeWork Inc", status: "BANKRUPT", riskScore: 88, signals: 8 },
  { ticker: "BBBYQ", name: "Bed Bath & Beyond", status: "BANKRUPT", riskScore: 95, signals: 10 },
];

const STEPS = [
  { number: 1, title: "Enter Ticker", description: "Type any stock ticker symbol" },
  { number: 2, title: "AI Fetches Filings", description: "We retrieve SEC 8-K, 10-K, 10-Q filings" },
  { number: 3, title: "Signal Extraction", description: "GPT-4o extracts bankruptcy warning signals" },
  { number: 4, title: "Risk Assessment", description: "Pattern matching against known bankruptcies" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-gray-50 to-white">
      {/* Navigation */}
      <nav className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
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
            <Link
              href="/pricing"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-6">
          Spot Bankruptcy Signals
          <br />
          <span className="text-blue-600">Before Headlines</span>
        </h1>
        <p className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto">
          Enter any stock ticker. Our AI analyzes SEC filings to find early warning signs
          that preceded major corporate bankruptcies.
        </p>

        <div className="flex justify-center mb-8">
          <TickerInput size="large" />
        </div>

        <p className="text-sm text-gray-500">
          Try: PLUG, TSLA, GME, or any US stock ticker
        </p>
      </section>

      {/* Social Proof */}
      <section className="bg-blue-600 text-white py-8">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-xl font-medium">
            &quot;Found warning signals 23 months before iRobot&apos;s bankruptcy filing&quot;
          </p>
        </div>
      </section>

      {/* Featured Analyses */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-center mb-4">Recent Bankruptcy Cases</h2>
        <p className="text-gray-600 text-center mb-10">
          See how our AI detected warning signals before these companies filed for bankruptcy
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {FEATURED_ANALYSES.map((analysis) => (
            <Link
              key={analysis.ticker}
              href={`/analysis/${analysis.ticker}`}
              className="bg-white rounded-xl shadow-lg p-6 hover:shadow-xl transition-shadow border border-gray-100"
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-2xl font-bold">{analysis.ticker}</span>
                  <span className="ml-2 px-2 py-0.5 bg-red-100 text-red-800 text-xs font-medium rounded">
                    {analysis.status}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-3xl font-bold text-red-600">{analysis.riskScore}</div>
                  <div className="text-xs text-gray-500">Risk Score</div>
                </div>
              </div>
              <div className="text-gray-600 mb-2">{analysis.name}</div>
              <div className="text-sm text-gray-500">
                {analysis.signals} warning signals detected
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-7xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">How It Works</h2>

          <div className="grid md:grid-cols-4 gap-8">
            {STEPS.map((step) => (
              <div key={step.number} className="text-center">
                <div className="w-12 h-12 bg-blue-600 text-white rounded-full flex items-center justify-center text-xl font-bold mx-auto mb-4">
                  {step.number}
                </div>
                <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
                <p className="text-gray-600 text-sm">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Signal Types */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <h2 className="text-3xl font-bold text-center mb-4">What We Detect</h2>
        <p className="text-gray-600 text-center mb-10">
          Our AI scans for 15+ types of bankruptcy warning signals
        </p>

        <div className="grid md:grid-cols-3 gap-4">
          {[
            { name: "Going Concern Warnings", desc: "Auditor doubts about survival", severity: "Critical" },
            { name: "Executive Departures", desc: "CEO/CFO resignations or terminations", severity: "High" },
            { name: "Mass Layoffs", desc: "Significant workforce reductions", severity: "High" },
            { name: "Debt Defaults", desc: "Missed payments, loan acceleration", severity: "Critical" },
            { name: "Delisting Warnings", desc: "Exchange compliance issues", severity: "High" },
            { name: "Covenant Violations", desc: "Loan agreement breaches", severity: "High" },
          ].map((signal, i) => (
            <div key={i} className="bg-white rounded-lg border border-gray-200 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium">{signal.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  signal.severity === "Critical" ? "bg-red-100 text-red-800" : "bg-orange-100 text-orange-800"
                }`}>
                  {signal.severity}
                </span>
              </div>
              <p className="text-sm text-gray-600">{signal.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="bg-blue-600 text-white py-16">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <h2 className="text-3xl font-bold mb-4">Ready to Analyze?</h2>
          <p className="text-xl opacity-90 mb-8">
            Start with a free analysis. No credit card required.
          </p>
          <div className="flex justify-center">
            <TickerInput size="large" />
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <h3 className="text-white font-bold text-lg mb-4">SEC Insights</h3>
              <p className="text-sm">
                AI-powered bankruptcy risk analysis using SEC filings.
              </p>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm">
                <li><Link href="/methodology" className="hover:text-white">Methodology</Link></li>
                <li><Link href="/pricing" className="hover:text-white">Pricing</Link></li>
                <li><Link href="/compare" className="hover:text-white">Compare</Link></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm">
                <li><a href="#" className="hover:text-white">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-white">Terms of Service</a></li>
                <li><a href="#" className="hover:text-white">Disclaimer</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-semibold mb-4">Disclaimer</h4>
              <p className="text-xs">
                This tool is for informational purposes only and does not constitute financial advice.
                Past performance does not guarantee future results.
              </p>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-8 pt-8 text-center text-sm">
            &copy; {new Date().getFullYear()} SEC Insights. All rights reserved.
          </div>
        </div>
      </footer>
    </main>
  );
}
