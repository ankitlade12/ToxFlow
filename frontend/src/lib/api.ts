import type {
  SingleBacktestResult,
  MonteCarloResult,
  MarketsResult,
  ScanResult,
  LiveAnalysisResult,
} from "./types";

const API_BASE = "http://localhost:8000";

export async function runSingleBacktest(params: {
  duration?: number;
  bucketVolume?: number;
  vpinWindow?: number;
  zThreshold?: number;
  capital?: number;
  seed?: number;
  useSynthesis?: boolean;
}): Promise<SingleBacktestResult> {
  const searchParams = new URLSearchParams();
  if (params.duration) searchParams.set("duration", String(params.duration));
  if (params.bucketVolume) searchParams.set("bucket_volume", String(params.bucketVolume));
  if (params.vpinWindow) searchParams.set("vpin_window", String(params.vpinWindow));
  if (params.zThreshold) searchParams.set("z_threshold", String(params.zThreshold));
  if (params.capital) searchParams.set("capital", String(params.capital));
  if (params.seed !== undefined) searchParams.set("seed", String(params.seed));
  if (params.useSynthesis !== undefined) searchParams.set("use_synthesis", String(params.useSynthesis));

  const res = await fetch(`${API_BASE}/api/backtest/single?${searchParams}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function runMonteCarlo(params: {
  simulations?: number;
  duration?: number;
  bucketVolume?: number;
  vpinWindow?: number;
  zThreshold?: number;
  capital?: number;
  useSynthesis?: boolean;
}): Promise<MonteCarloResult> {
  const searchParams = new URLSearchParams();
  if (params.simulations) searchParams.set("simulations", String(params.simulations));
  if (params.duration) searchParams.set("duration", String(params.duration));
  if (params.bucketVolume) searchParams.set("bucket_volume", String(params.bucketVolume));
  if (params.vpinWindow) searchParams.set("vpin_window", String(params.vpinWindow));
  if (params.zThreshold) searchParams.set("z_threshold", String(params.zThreshold));
  if (params.capital) searchParams.set("capital", String(params.capital));
  if (params.useSynthesis !== undefined) searchParams.set("use_synthesis", String(params.useSynthesis));

  const res = await fetch(`${API_BASE}/api/backtest/monte-carlo?${searchParams}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

// WebSocket URL for the real-time VPIN stream of a market.
export function streamUrl(conditionId: string): string {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/api/stream/${conditionId}`;
}

// ── Live market endpoints (real Polymarket data via Synthesis) ─────────

export async function listMarkets(params: {
  limit?: number;
  query?: string;
}): Promise<MarketsResult> {
  const sp = new URLSearchParams();
  if (params.limit) sp.set("limit", String(params.limit));
  if (params.query) sp.set("query", params.query);
  const res = await fetch(`${API_BASE}/api/markets?${sp}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function scanMarkets(params: {
  top?: number;
  query?: string;
  bucketVolume?: number;
  vpinWindow?: number;
  zThreshold?: number;
  maxTrades?: number;
}): Promise<ScanResult> {
  const sp = new URLSearchParams();
  if (params.top) sp.set("top", String(params.top));
  if (params.query) sp.set("query", params.query);
  if (params.bucketVolume) sp.set("bucket_volume", String(params.bucketVolume));
  if (params.vpinWindow) sp.set("vpin_window", String(params.vpinWindow));
  if (params.zThreshold) sp.set("z_threshold", String(params.zThreshold));
  if (params.maxTrades) sp.set("max_trades", String(params.maxTrades));
  const res = await fetch(`${API_BASE}/api/scan?${sp}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function analyzeMarket(params: {
  conditionId: string;
  bucketVolume?: number;
  vpinWindow?: number;
  zThreshold?: number;
  maxTrades?: number;
}): Promise<LiveAnalysisResult> {
  const sp = new URLSearchParams();
  sp.set("condition_id", params.conditionId);
  if (params.bucketVolume) sp.set("bucket_volume", String(params.bucketVolume));
  if (params.vpinWindow) sp.set("vpin_window", String(params.vpinWindow));
  if (params.zThreshold) sp.set("z_threshold", String(params.zThreshold));
  if (params.maxTrades) sp.set("max_trades", String(params.maxTrades));
  const res = await fetch(`${API_BASE}/api/analyze?${sp}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || `API error: ${res.status}`);
  }
  return res.json();
}
