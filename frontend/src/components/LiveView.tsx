import { useCallback, useEffect, useRef, useState } from "react";
import {
  Radar,
  Search,
  RefreshCw,
  Loader2,
  Bell,
  X,
  Clock3,
  ShieldCheck,
  Radio,
  ChevronDown,
} from "lucide-react";
import { scanMarkets, analyzeMarket } from "../lib/api";
import type { ScanRow, LiveAnalysisResult } from "../lib/types";
import LiveRadar from "./LiveRadar";
import LiveStreamPanel from "./LiveStreamPanel";
import SmartMoneyPanel from "./SmartMoneyPanel";
import DecisionBrief from "./DecisionBrief";
import StatsCards from "./StatsCards";
import VPINChart from "./VPINChart";
import PnlChart from "./PnlChart";
import SignalHeatmap from "./SignalHeatmap";
import OpportunityRadar from "./OpportunityRadar";
import TradeTable from "./TradeTable";

const WATCHLIST_KEY = "toxflow_watchlist";
const REFRESH_SECONDS = 30;

interface AlertItem {
  key: string;
  conditionId: string;
  question: string;
  kind: string;
  vpin: number;
  time: number;
}

function loadWatchlist(): Set<string> {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    return new Set(raw ? (JSON.parse(raw) as string[]) : []);
  } catch {
    return new Set();
  }
}

export default function LiveView() {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<ScanRow[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const [lastScanAt, setLastScanAt] = useState<number | null>(null);

  const [autoRefresh, setAutoRefresh] = useState(false);
  const [watchlist, setWatchlist] = useState<Set<string>>(loadWatchlist);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [alertedIds, setAlertedIds] = useState<Set<string>>(new Set());

  const [analysis, setAnalysis] = useState<LiveAnalysisResult | null>(null);
  const [selectedMarket, setSelectedMarket] = useState<ScanRow | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [showBaseline, setShowBaseline] = useState(false);

  const prevScan = useRef<Map<string, ScanRow>>(new Map());
  const watchlistRef = useRef(watchlist);
  watchlistRef.current = watchlist;
  const analysisRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify([...watchlist]));
    } catch {
      /* ignore */
    }
  }, [watchlist]);

  // Bring the analysis into view when a market is selected (it renders below
  // the radar table, which can be long).
  useEffect(() => {
    if (!selectedMarket) return;
    const t = setTimeout(
      () => analysisRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }),
      60,
    );
    return () => clearTimeout(t);
  }, [selectedMarket]);

  const detectAlerts = useCallback((next: ScanRow[]) => {
    const prev = prevScan.current;
    const fresh: AlertItem[] = [];
    const flagged = new Set<string>();
    const now = Date.now();

    for (const r of next) {
      const p = prev.get(r.conditionId);
      const watched = watchlistRef.current.has(r.conditionId);
      const crossedToxic = !!p && p.vpin < 0.8 && r.vpin >= 0.8;
      const newDivergence = r.divergence && (!p || !p.divergence);
      const surge = r.vpinMomentum > 0.04 && r.vpin >= 0.7;

      let kind: string | null = null;
      if (crossedToxic) kind = "Turned toxic (VPIN ≥ 0.80)";
      else if (newDivergence) kind = "Smart-money divergence opened";
      else if (surge && watched) kind = "Toxicity surging";

      // Alert on watched markets for any trigger, or any market that newly
      // crosses a high toxicity bar (so the radar surfaces hot markets too).
      if (kind && (watched || (crossedToxic && r.vpin >= 0.85))) {
        flagged.add(r.conditionId);
        fresh.push({
          key: `${r.conditionId}-${now}`,
          conditionId: r.conditionId,
          question: r.question,
          kind: watched ? `★ ${kind}` : kind,
          vpin: r.vpin,
          time: now,
        });
      }
    }

    if (fresh.length > 0) {
      setAlerts((prevAlerts) => [...fresh, ...prevAlerts].slice(0, 12));
    }
    setAlertedIds(flagged);
    prevScan.current = new Map(next.map((r) => [r.conditionId, r]));
  }, []);

  const runScan = useCallback(async () => {
    setScanning(true);
    setScanError(null);
    try {
      const res = await scanMarkets({ top: 12, query: query || undefined, maxTrades: 1200 });
      setRows(res.markets);
      detectAlerts(res.markets);
      setLastScanAt(Date.now());
    } catch (e) {
      setScanError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  }, [query, detectAlerts]);

  // Auto-refresh polling
  useEffect(() => {
    if (!autoRefresh) return;
    const id = setInterval(runScan, REFRESH_SECONDS * 1000);
    return () => clearInterval(id);
  }, [autoRefresh, runScan]);

  const toggleWatch = (id: string) => {
    setWatchlist((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleAnalyze = async (row: ScanRow) => {
    setSelectedMarket(row);
    setStreaming(false);
    setAnalyzing(true);
    setAnalyzeError(null);
    setAnalysis(null);
    try {
      const res = await analyzeMarket({ conditionId: row.conditionId, maxTrades: 4000 });
      setAnalysis(res);
    } catch (e) {
      setAnalyzeError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Radar controls */}
      <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
              <Radar className="h-4 w-4 text-blue-400" />
              Live Toxicity Radar
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Real Polymarket trades via Synthesis · ranked by toxicity
              (VPIN adjusted for trading activity) · pure orderflow, no forecast
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-500" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runScan()}
                placeholder="Search markets (e.g. bitcoin, fed, election)"
                className="w-64 rounded-md border border-gray-600 bg-gray-700/50 py-1.5 pl-8 pr-2 text-sm text-gray-200 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <button
              onClick={runScan}
              disabled={scanning}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:bg-gray-600"
            >
              {scanning ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Radar className="h-4 w-4" />
              )}
              Scan
            </button>
            <button
              onClick={() => setAutoRefresh((v) => !v)}
              title={`Auto-refresh every ${REFRESH_SECONDS}s`}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                autoRefresh
                  ? "bg-emerald-600/80 text-white hover:bg-emerald-500"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
            >
              {autoRefresh ? (
                <span className={`h-2 w-2 rounded-full bg-white ${scanning ? "animate-ping" : "animate-pulse"}`} />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              {autoRefresh ? "Live" : "Auto"}
            </button>
          </div>
        </div>

        {lastScanAt && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-gray-500">
            <Clock3 className="h-3 w-3" />
            Last scan {new Date(lastScanAt).toLocaleTimeString()}
            {watchlist.size > 0 && ` · watching ${watchlist.size}`}
          </div>
        )}

        {scanError && (
          <div className="mt-3 rounded-lg border border-red-700/50 bg-red-900/30 p-3 text-sm text-red-400">
            {scanError} — is the API running on :8000?
          </div>
        )}

        <div className="mt-3">
          <LiveRadar
            rows={rows}
            scanning={scanning}
            watchlist={watchlist}
            alertedIds={alertedIds}
            selectedId={selectedMarket?.conditionId ?? null}
            onToggleWatch={toggleWatch}
            onAnalyze={handleAnalyze}
          />
        </div>
      </div>

      {/* Alerts feed */}
      {alerts.length > 0 && (
        <div className="bg-gray-800/50 border border-amber-500/20 rounded-lg p-4">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-300">
            <Bell className="h-4 w-4" />
            Alerts
            <span className="rounded-full bg-amber-400/15 px-2 py-0.5 text-[11px] text-amber-200">
              {alerts.length}
            </span>
          </div>
          <div className="space-y-1.5">
            {alerts.map((a) => (
              <div
                key={a.key}
                className="flex items-center justify-between gap-3 rounded-md bg-gray-900/40 px-3 py-2 text-xs"
              >
                <div className="min-w-0">
                  <span className="font-medium text-amber-200">{a.kind}</span>
                  <span className="ml-2 truncate text-gray-400">{a.question}</span>
                </div>
                <span className="shrink-0 font-mono text-gray-500">
                  VPIN {a.vpin.toFixed(2)} · {new Date(a.time).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {rows.length === 0 && !scanning && !scanError && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center">
            <Radar className="mx-auto mb-3 h-10 w-10 text-gray-600" />
            <h2 className="mb-1 text-lg font-medium text-gray-400">
              Scan live Polymarket markets
            </h2>
            <p className="text-sm text-gray-500">
              Hit <span className="text-gray-300">Scan</span> to rank real markets
              by orderflow toxicity right now.
            </p>
          </div>
        </div>
      )}

      {/* Analysis drill-down */}
      {selectedMarket && (
        <div className="space-y-4 scroll-mt-4" ref={analysisRef}>
          <div className="flex items-start justify-between gap-3 rounded-lg border border-blue-500/30 bg-gray-800/50 p-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-emerald-400/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-300">
                  LIVE
                </span>
                <span className="text-xs text-gray-500">
                  real trades · no forecast · no outcome peeking
                </span>
              </div>
              <h2 className="mt-1 truncate text-base font-semibold text-gray-100">
                {selectedMarket.question}
              </h2>
              {analysis && (
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-gray-500">
                  <span>{analysis.numTrades.toLocaleString()} trades</span>
                  <span>tape spans {(analysis.tapeSpanSeconds / 3600).toFixed(1)}h</span>
                  <span>price {(analysis.latestPrice * 100).toFixed(1)}c</span>
                </div>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                onClick={() => setStreaming((v) => !v)}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  streaming
                    ? "bg-emerald-600/80 text-white hover:bg-emerald-500"
                    : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                }`}
                title="Stream real-time trades & VPIN over WebSocket"
              >
                <Radio className={`h-3.5 w-3.5 ${streaming ? "animate-pulse" : ""}`} />
                {streaming ? "Streaming" : "Go Live"}
              </button>
              <button
                onClick={() => {
                  setSelectedMarket(null);
                  setAnalysis(null);
                  setAnalyzeError(null);
                  setStreaming(false);
                }}
                className="text-gray-500 hover:text-gray-300"
                title="Close analysis"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>

          {streaming && selectedMarket && (
            <LiveStreamPanel conditionId={selectedMarket.conditionId} />
          )}

          {analyzing && (
            <div className="flex items-center justify-center py-16">
              <div className="text-center">
                <Loader2 className="mx-auto mb-3 h-7 w-7 animate-spin text-blue-400" />
                <p className="text-sm text-gray-400">
                  Pulling real trades & running VPIN…
                </p>
              </div>
            </div>
          )}

          {analyzeError && (
            <div className="rounded-lg border border-red-700/50 bg-red-900/30 p-3 text-sm text-red-400">
              {analyzeError}
            </div>
          )}

          {analysis && !analyzing && (
            <div className="space-y-4">
              {/* ── Detection layer (the real signal) ── */}
              <DecisionBrief result={analysis} />

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <VPINChart
                  vpinSeries={analysis.vpinSeries}
                  priceSeries={analysis.priceSeries}
                />
                <SmartMoneyPanel smartMoney={analysis.smartMoney} />
              </div>

              <div className="grid grid-cols-1 xl:grid-cols-[1.2fr_1fr] gap-4">
                <SignalHeatmap signals={analysis.signals} />
                <OpportunityRadar
                  opportunities={analysis.opportunities}
                  axisTimes={analysis.signals.map((s) => s.time)}
                />
              </div>

              {/* ── Strategy baseline (collapsible, honest) ── */}
              <div className="rounded-lg border border-gray-700/50 bg-gray-800/30">
                <button
                  onClick={() => setShowBaseline((v) => !v)}
                  className="flex w-full items-center justify-between gap-3 p-4 text-left"
                >
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <ShieldCheck className="h-4 w-4 shrink-0 text-gray-500" />
                    <span className="text-sm font-medium text-gray-300">
                      Strategy baseline
                    </span>
                    <span className="text-xs text-gray-500">
                      naive momentum replayed on this real tape ·{" "}
                      <span
                        className={
                          analysis.stats.totalPnl >= 0
                            ? "text-emerald-400"
                            : "text-red-400"
                        }
                      >
                        {analysis.stats.totalPnl >= 0 ? "+" : ""}
                        {(analysis.stats.roi * 100).toFixed(1)}% ROI
                      </span>
                    </span>
                  </div>
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-gray-500 transition-transform ${
                      showBaseline ? "rotate-180" : ""
                    }`}
                  />
                </button>
                {showBaseline && (
                  <div className="space-y-4 border-t border-gray-700/50 p-4">
                    <p className="text-xs leading-relaxed text-gray-500">
                      A deliberately simple "trade the VPIN spike" rule replayed
                      on this market's real trades (stops/targets fill at level,
                      1% taker fee). Prediction markets are efficient, so this
                      baseline often loses — that's expected and honest.{" "}
                      <span className="text-gray-400">
                        ToxFlow's value is the detection layer above; this is a
                        stress test, not the product.
                      </span>
                    </p>
                    <StatsCards stats={analysis.stats} />
                    <PnlChart pnlCurve={analysis.pnlCurve} />
                    <TradeTable trades={analysis.pnlCurve} />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
