import Link from "next/link";

const PRICING_TIERS = [
  {
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Perfect for trying out the platform",
    features: [
      "1 analysis per account",
      "Basic signal extraction",
      "7-day cached results",
      "Signal timeline view",
    ],
    cta: "Get Started",
    highlighted: false,
  },
  {
    name: "Pro",
    price: "$29",
    period: "per month",
    description: "For serious investors and analysts",
    features: [
      "Unlimited analyses",
      "Real-time signal alerts",
      "API access",
      "Compare companies",
      "Export reports (PDF/CSV)",
      "Priority support",
      "Pattern matching insights",
    ],
    cta: "Start Free Trial",
    highlighted: true,
  },
  {
    name: "Enterprise",
    price: "Custom",
    period: "",
    description: "For teams and institutions",
    features: [
      "Everything in Pro",
      "Team management",
      "Custom integrations",
      "Dedicated account manager",
      "SLA guarantee",
      "Custom signal types",
      "White-label options",
    ],
    cta: "Contact Sales",
    highlighted: false,
  },
];

export default function PricingPage() {
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
            <Link href="/" className="text-gray-600 hover:text-gray-900">
              Analyze
            </Link>
          </div>
        </div>
      </nav>

      {/* Header */}
      <section className="py-16 text-center">
        <h1 className="text-4xl font-bold mb-4">Simple, Transparent Pricing</h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          Start for free, upgrade when you need more. No hidden fees.
        </p>
      </section>

      {/* Pricing Cards */}
      <section className="max-w-7xl mx-auto px-4 pb-16">
        <div className="grid md:grid-cols-3 gap-8">
          {PRICING_TIERS.map((tier) => (
            <div
              key={tier.name}
              className={`bg-white rounded-xl shadow-lg p-8 relative ${
                tier.highlighted
                  ? "ring-2 ring-blue-600 transform md:-translate-y-4"
                  : ""
              }`}
            >
              {tier.highlighted && (
                <div className="absolute top-0 left-1/2 transform -translate-x-1/2 -translate-y-1/2">
                  <span className="bg-blue-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h2 className="text-2xl font-bold mb-2">{tier.name}</h2>
                <div className="mb-2">
                  <span className="text-4xl font-bold">{tier.price}</span>
                  {tier.period && (
                    <span className="text-gray-500 ml-1">/{tier.period}</span>
                  )}
                </div>
                <p className="text-gray-600">{tier.description}</p>
              </div>

              <ul className="space-y-3 mb-8">
                {tier.features.map((feature, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <svg
                      className="w-5 h-5 text-green-500 flex-shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                className={`w-full py-3 rounded-lg font-semibold transition-colors ${
                  tier.highlighted
                    ? "bg-blue-600 text-white hover:bg-blue-700"
                    : "bg-gray-100 text-gray-800 hover:bg-gray-200"
                }`}
              >
                {tier.cta}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* FAQ */}
      <section className="bg-white py-16">
        <div className="max-w-3xl mx-auto px-4">
          <h2 className="text-3xl font-bold text-center mb-12">
            Frequently Asked Questions
          </h2>

          <div className="space-y-6">
            {[
              {
                q: "How does the free tier work?",
                a: "The free tier gives you one complete analysis. Once used, you can view your cached result for 7 days. To run more analyses, upgrade to Pro.",
              },
              {
                q: "What SEC filings do you analyze?",
                a: "We analyze 8-K filings (current reports), 10-K (annual reports), and 10-Q (quarterly reports) from the past 24 months.",
              },
              {
                q: "How accurate is the risk score?",
                a: "Our AI has been trained on historical bankruptcy cases and achieved pattern recognition of warning signals up to 23 months before filing. However, this is not a guarantee of future outcomes.",
              },
              {
                q: "Can I cancel anytime?",
                a: "Yes, Pro subscriptions can be cancelled at any time. You'll retain access until the end of your billing period.",
              },
              {
                q: "Do you offer refunds?",
                a: "We offer a 14-day money-back guarantee for Pro subscriptions if you're not satisfied.",
              },
            ].map((faq, i) => (
              <div key={i} className="border-b border-gray-200 pb-6">
                <h3 className="font-semibold text-lg mb-2">{faq.q}</h3>
                <p className="text-gray-600">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-gray-900 text-gray-400 py-8">
        <div className="max-w-7xl mx-auto px-4 text-center text-sm">
          &copy; {new Date().getFullYear()} SEC Insights. All rights reserved.
        </div>
      </footer>
    </main>
  );
}
