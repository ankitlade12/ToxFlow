export interface BacktestConfig {
  bucketVolume: number;
  vpinWindow: number;
  zThreshold: number;
  duration: number;
  seed: number;
}

export interface BacktestStats {
  totalPnl: number;
  roi: number;
  winRate: number;
  profitFactor: number;
  numTrades: number;
  avgWin: number;
  avgLoss: number;
  avgTradePnl: number;
  maxDrawdown: number;
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
  recommendedSize: number;
  vpin: number;
  dvpin: number;
  zScore: number;
}

export interface PnlPoint {
  time: number;
  pnl: number;
  tradePnl: number;
  side: string;
  size: number;
  entryPrice: number;
  exitPrice: number;
  signalStrength: number;
  vpinAtEntry: number;
  synthEdgeAtEntry: number | null;
}

export interface SingleBacktestResult {
  outcome: string;
  numTrades: number;
  config: BacktestConfig;
  stats: BacktestStats;
  decisionBrief: DecisionBrief;
  riskSummary: RiskSummary;
  marketQuality: MarketQuality;
  opportunities: Opportunity[];
  benchmark: Benchmark | null;
  priceSeries: PricePoint[];
  vpinSeries: VPINPoint[];
  signals: SignalPoint[];
  pnlCurve: PnlPoint[];
}

export interface DecisionBrief {
  action: string;
  confidence: number;
  confidenceLabel: string;
  flowBias: string;
  latestPrice: number;
  latestSignalTime: number | null;
  signalAgeSeconds: number | null;
  recommendedSide: string | null;
  reasons: string[];
}

export interface RiskSummary {
  suggestedPosition: number;
  capitalAtRiskPct: number;
  maxPositionPct: number;
  stopLossPct: number;
  profitTargetPct: number;
  maxHoldSeconds: number;
  maxConcurrentPositions: number;
  roundTripFeeBps: number;
  feeDragPct: number;
  riskFlags: string[];
}

export interface MarketQuality {
  totalVolume: number;
  uniqueWallets: number;
  buySellImbalance: number;
  largeTradePct: number;
  topWalletVolumePct: number;
  spikeCount: number;
  latestVpin: number;
  toxicityRegime: string;
  liquidityScore: number;
}

export interface Opportunity {
  rank: number;
  time: number;
  action: string;
  side: string;
  strength: number;
  toxicity: number;
  vpin: number;
  dvpin: number;
  zScore: number;
  synthEdge: number | null;
  recommendedSize: number;
  rationale: string;
}

export interface Benchmark {
  label: string;
  vpinOnlyPnl: number;
  vpinOnlyWinRate: number;
  vpinOnlyTrades: number;
  compositeLift: number;
  tradeDelta: number;
  winRateDelta: number;
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

// ── Live (real Polymarket data) ──────────────────────────────────────

export interface MarketRow {
  conditionId: string;
  question: string;
  outcomeLabel: string | null;
  volume: number;
  liquidity: number;
  yesPrice: number;
  noPrice: number;
  resolved: boolean;
  endDate: string | null;
}

export interface MarketsResult {
  count: number;
  markets: MarketRow[];
}

export interface ScanRow {
  conditionId: string;
  question: string;
  eventTitle: string | null;
  volume: number;
  latestPrice: number | null;
  vpin: number;
  toxicityScore: number;
  confidence: number;
  dvpin: number;
  zScore: number;
  vpinMomentum: number;
  spikeCount: number;
  numTrades: number;
  flowBias: string;
  smartVolumePct: number;
  divergence: boolean;
}

export interface ScanResult {
  scanned: number;
  markets: ScanRow[];
}

export interface SmartMoneyLeader {
  address: string;
  volume: number;
  trades: number;
  avgSize: number;
  netDirection: number;
  conviction: number;
  leadership: number;
  score: number;
  side: string;
}

export interface SmartMoney {
  informedWallets: number;
  totalWallets: number;
  smartVolumePct: number;
  smartDirection: number;
  retailDirection: number;
  divergence: boolean;
  convictionScore: number;
  flowBias: string;
  leaders: SmartMoneyLeader[];
}

export interface LiveAnalysisResult {
  dataSource: string;
  forecastMode: string;
  conditionId: string;
  numTrades: number;
  tapeSpanSeconds: number;
  latestPrice: number;
  config: { bucketVolume: number; vpinWindow: number; zThreshold: number };
  stats: BacktestStats;
  decisionBrief: DecisionBrief;
  riskSummary: RiskSummary;
  marketQuality: MarketQuality;
  smartMoney: SmartMoney;
  opportunities: Opportunity[];
  benchmark: Benchmark | null;
  priceSeries: PricePoint[];
  vpinSeries: VPINPoint[];
  signals: SignalPoint[];
  pnlCurve: PnlPoint[];
}
