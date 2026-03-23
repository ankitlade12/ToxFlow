export interface BacktestConfig {
  bucketVolume: number;
  vpinWindow: number;
  zThreshold: number;
  duration: number;
  seed: number;
}

export interface BacktestStats {
  totalPnl: number;
  winRate: number;
  profitFactor: number;
  numTrades: number;
  avgWin: number;
  avgLoss: number;
  totalFees: number;
  finalCapital: number;
}

export interface PricePoint {
  time: number;
  price: number;
  size: number;
  side: string;
}

export interface VPINPoint {
  time: number;
  vpin: number;
  dvpin: number;
  zScore: number;
  isSpike: boolean;
  bucketId: number;
}

export interface SignalPoint {
  time: number;
  strength: number;
  direction: number;
  shouldTrade: boolean;
  side: string | null;
  toxicity: number;
  synthEdge: number | null;
}

export interface PnlPoint {
  time: number;
  pnl: number;
  tradePnl: number;
  side: string;
  entryPrice: number;
  exitPrice: number;
  signalStrength: number;
  vpinAtEntry: number;
}

export interface SingleBacktestResult {
  outcome: string;
  numTrades: number;
  config: BacktestConfig;
  stats: BacktestStats;
  priceSeries: PricePoint[];
  vpinSeries: VPINPoint[];
  signals: SignalPoint[];
  pnlCurve: PnlPoint[];
}

export interface MCSimResult {
  pnl: number;
  winRate: number;
  sharpe: number;
  maxDrawdown: number;
  profitFactor: number;
  numTrades: number;
  totalFees: number;
}

export interface MCSummary {
  meanPnl: number;
  medianPnl: number;
  stdPnl: number;
  pnl5th: number;
  pnl95th: number;
  meanWinRate: number;
  meanSharpe: number;
  meanDrawdown: number;
  profitableRuns: number;
  profitableRunsPct: number;
  meanTradeCount: number;
}

export interface MonteCarloResult {
  simulations: number;
  results: MCSimResult[];
  summary: MCSummary;
}
