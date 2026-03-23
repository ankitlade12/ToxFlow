import { useState } from "react";
import { runSingleBacktest, runMonteCarlo } from "./lib/api";
import type { SingleBacktestResult, MonteCarloResult } from "./lib/types";
import ConfigPanel, { type ConfigParams } from "./components/ConfigPanel";
import StatsCards from "./components/StatsCards";
import VPINChart from "./components/VPINChart";
import PnlChart from "./components/PnlChart";
import SignalHeatmap from "./components/SignalHeatmap";
import MonteCarloChart from "./components/MonteCarloChart";
import TradeTable from "./components/TradeTable";
import { Activity } from "lucide-react";
import "./index.css";

type Tab = "single" | "montecarlo";

export default function App() {
  const [tab, setTab] = useState<Tab>("single");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [singleResult, setSingleResult] =
    useState<SingleBacktestResult | null>(null);
  const [mcResult, setMcResult] = useState<MonteCarloResult | null>(null);

  const handleRunSingle = async (params: ConfigParams) => {
    setLoading(true);
    setError(null);
    try {
      const result = await runSingleBacktest(params);
      setSingleResult(result);
      setTab("single");
    } catch (e: any) {
      setError(e.message || "Failed to run backtest");
    } finally {
      setLoading(false);
    }
  };

  const handleRunMonteCarlo = async (
    params: ConfigParams & { simulations: number },
  ) => {
    setLoading(true);
    setError(null);
    try {
      const result = await runMonteCarlo(params);
      setMcResult(result);
      setTab("montecarlo");
    } catch (e: any) {
      setError(e.message || "Failed to run Monte Carlo");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 px-6 py-4">
        <div className="max-w-[1400px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600/20 rounded-lg">
              <Activity className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight">ToxFlow</h1>
              <p className="text-xs text-gray-500">
                Polymarket Orderflow Toxicity Engine
              </p>
            </div>
          </div>
          <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setTab("single")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                tab === "single"
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Single Backtest
            </button>
            <button
              onClick={() => setTab("montecarlo")}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                tab === "montecarlo"
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              Monte Carlo
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-[1400px] mx-auto px-6 py-6 space-y-4">
        <ConfigPanel
          onRunSingle={handleRunSingle}
          onRunMonteCarlo={handleRunMonteCarlo}
          loading={loading}
        />

        {error && (
          <div className="bg-red-900/30 border border-red-700/50 rounded-lg p-3 text-sm text-red-400">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <div className="w-8 h-8 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-sm text-gray-400">
                {tab === "montecarlo"
                  ? "Running Monte Carlo simulations..."
                  : "Running backtest..."}
              </p>
            </div>
          </div>
        )}

        {/* Single Backtest Results */}
        {tab === "single" && singleResult && !loading && (
          <div className="space-y-4">
            <StatsCards
              stats={singleResult.stats}
              outcome={singleResult.outcome}
            />

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <VPINChart
                vpinSeries={singleResult.vpinSeries}
                priceSeries={singleResult.priceSeries}
              />
              <PnlChart pnlCurve={singleResult.pnlCurve} />
            </div>

            <SignalHeatmap signals={singleResult.signals} />
            <TradeTable trades={singleResult.pnlCurve} />
          </div>
        )}

        {/* Monte Carlo Results */}
        {tab === "montecarlo" && mcResult && !loading && (
          <MonteCarloChart data={mcResult} />
        )}

        {/* Empty state */}
        {!singleResult && !mcResult && !loading && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Activity className="w-12 h-12 text-gray-600 mx-auto mb-4" />
              <h2 className="text-lg font-medium text-gray-400 mb-2">
                No results yet
              </h2>
              <p className="text-sm text-gray-500">
                Configure parameters above and run a backtest to see VPIN
                analysis
              </p>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
