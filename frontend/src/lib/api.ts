import type { SingleBacktestResult, MonteCarloResult } from "./types";

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
