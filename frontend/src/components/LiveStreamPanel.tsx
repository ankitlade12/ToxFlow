import { useEffect, useRef, useState } from "react";
import { streamUrl } from "../lib/api";
import {
  Radio,
  Loader2,
  WifiOff,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";

interface Props {
  conditionId: string;
}

type Status = "connecting" | "live" | "error" | "closed";

interface Tick {
  time: number;
  price: number;
  size: number;
  side: string;
  wallet?: string | null;
  isSpike?: boolean;
}

interface SparkPoint {
  time: number;
  vpin: number;
}

function toxicityColor(vpin: number) {
  if (vpin >= 0.85) return "#ef4444";
  if (vpin >= 0.7) return "#f97316";
  if (vpin >= 0.5) return "#eab308";
  return "#22c55e";
}

function Sparkline({ points }: { points: SparkPoint[] }) {
  if (points.length < 2) {
    return (
      <div className="flex h-16 items-center justify-center text-xs text-gray-600">
        warming up…
      </div>
    );
  }
  const w = 100;
  const h = 100;
  const xs = points.map((_, i) => (i / (points.length - 1)) * w);
  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xs[i].toFixed(2)} ${(h - p.vpin * h).toFixed(2)}`)
    .join(" ");
  const last = points[points.length - 1].vpin;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="h-16 w-full">
      <line x1="0" y1={h - 0.8 * h} x2={w} y2={h - 0.8 * h} stroke="#ef4444" strokeWidth="0.5" strokeDasharray="2 2" opacity="0.5" />
      <path d={path} fill="none" stroke={toxicityColor(last)} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export default function LiveStreamPanel({ conditionId }: Props) {
  const [status, setStatus] = useState<Status>("connecting");
  const [vpin, setVpin] = useState<number | null>(null);
  const [dvpin, setDvpin] = useState<number | null>(null);
  const [warmTrades, setWarmTrades] = useState(0);
  const [liveCount, setLiveCount] = useState(0);
  const [spikeCount, setSpikeCount] = useState(0);
  const [spark, setSpark] = useState<SparkPoint[]>([]);
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [spikeFlash, setSpikeFlash] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    setStatus("connecting");
    setVpin(null);
    setSpark([]);
    setTicks([]);
    setLiveCount(0);
    setSpikeCount(0);
    setErrorMsg(null);

    let closed = false;
    const ws = new WebSocket(streamUrl(conditionId));
    wsRef.current = ws;

    ws.onopen = () => !closed && setStatus("live");
    ws.onmessage = (ev) => {
      let m: Record<string, unknown>;
      try {
        m = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (m.type === "ready") {
        setWarmTrades(Number(m.warmTrades) || 0);
        const hist = ((m.vpinHistory as SparkPoint[]) || []).map((h) => ({
          time: h.time,
          vpin: h.vpin,
        }));
        setSpark(hist);
        if (hist.length) setVpin(hist[hist.length - 1].vpin);
        const histRaw = (m.vpinHistory as Array<{ dvpin: number }>) || [];
        if (histRaw.length) setDvpin(histRaw[histRaw.length - 1].dvpin);
        setStatus("live");
      } else if (m.type === "trade") {
        setLiveCount((c) => c + 1);
        setTicks((prev) =>
          [
            {
              time: Number(m.time),
              price: Number(m.price),
              size: Number(m.size),
              side: String(m.side),
              wallet: (m.wallet as string) ?? null,
              isSpike: Boolean(m.isSpike),
            },
            ...prev,
          ].slice(0, 24),
        );
        if (m.vpin !== undefined) {
          setVpin(Number(m.vpin));
          setDvpin(Number(m.dvpin));
          setSpark((prev) => [...prev, { time: Number(m.time), vpin: Number(m.vpin) }].slice(-120));
        }
        if (m.isSpike) {
          setSpikeCount((c) => c + 1);
          setSpikeFlash(true);
          setTimeout(() => setSpikeFlash(false), 1500);
        }
      } else if (m.type === "error") {
        setErrorMsg(String(m.detail));
        setStatus("error");
      }
    };
    ws.onerror = () => !closed && setStatus("error");
    ws.onclose = () => !closed && setStatus((s) => (s === "error" ? s : "closed"));

    return () => {
      closed = true;
      ws.close();
    };
  }, [conditionId]);

  const statusBadge = {
    connecting: { label: "Connecting", cls: "text-amber-300 bg-amber-400/10", icon: Loader2, spin: true },
    live: { label: "Streaming live", cls: "text-emerald-300 bg-emerald-400/10", icon: Radio, spin: false },
    error: { label: "Stream error", cls: "text-red-300 bg-red-400/10", icon: WifiOff, spin: false },
    closed: { label: "Stream closed", cls: "text-gray-300 bg-gray-700/60", icon: WifiOff, spin: false },
  }[status];
  const StatusIcon = statusBadge.icon;
  const dvpinYes = (dvpin ?? 0) >= 0;

  return (
    <div
      className={`rounded-lg border bg-gray-800/50 p-4 transition-colors ${
        spikeFlash ? "border-red-500/70" : "border-gray-700/50"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-300">
          <Radio className="h-4 w-4 text-blue-400" />
          Live VPIN Stream
        </div>
        <div className={`flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium ${statusBadge.cls}`}>
          <StatusIcon className={`h-3.5 w-3.5 ${statusBadge.spin ? "animate-spin" : ""}`} />
          {statusBadge.label}
        </div>
      </div>

      {errorMsg && (
        <div className="mt-3 rounded-md border border-red-700/40 bg-red-900/20 p-2 text-xs text-red-300">
          {errorMsg}
        </div>
      )}

      <div className="mt-4 grid grid-cols-[auto_1fr] items-center gap-4">
        <div>
          <div className="text-xs text-gray-500">Current VPIN</div>
          <div
            className="text-3xl font-bold tabular-nums"
            style={{ color: vpin != null ? toxicityColor(vpin) : "#6b7280" }}
          >
            {vpin != null ? vpin.toFixed(3) : "—"}
          </div>
          <div
            className={`mt-1 inline-flex items-center gap-1 text-xs ${
              dvpinYes ? "text-emerald-300" : "text-red-300"
            }`}
          >
            {dvpinYes ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            flow leans {dvpinYes ? "YES" : "NO"}
          </div>
        </div>
        <Sparkline points={spark} />
      </div>

      <div className="mt-3 flex items-center gap-4 border-t border-gray-700/50 pt-3 text-xs text-gray-400">
        <span>warmed {warmTrades.toLocaleString()}</span>
        <span className="text-emerald-300">live +{liveCount}</span>
        <span className="inline-flex items-center gap-1 text-amber-300">
          <Zap className="h-3 w-3" />
          {spikeCount} spikes
        </span>
      </div>

      {/* Live trade ticker */}
      <div className="mt-3 max-h-44 overflow-y-auto">
        {ticks.length === 0 ? (
          <div className="py-4 text-center text-xs text-gray-600">
            {status === "live"
              ? "Connected — waiting for the next live execution…"
              : "—"}
          </div>
        ) : (
          <table className="w-full text-xs">
            <tbody>
              {ticks.map((t, i) => {
                const isBuy = t.side === "buy";
                return (
                  <tr
                    key={`${t.time}-${i}`}
                    className={`border-b border-gray-700/30 last:border-0 ${
                      t.isSpike ? "bg-red-500/10" : ""
                    }`}
                  >
                    <td className="py-1.5">
                      <span className={`inline-flex items-center gap-1 ${isBuy ? "text-emerald-300" : "text-red-300"}`}>
                        {isBuy ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                        {isBuy ? "BUY" : "SELL"}
                      </span>
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-gray-300">
                      {(t.price * 100).toFixed(1)}c
                    </td>
                    <td className="py-1.5 text-right tabular-nums text-gray-400">
                      ${t.size.toFixed(0)}
                    </td>
                    <td className="py-1.5 text-right">
                      {t.isSpike && (
                        <span className="inline-flex items-center gap-0.5 rounded bg-red-400/15 px-1.5 py-0.5 text-[10px] font-semibold text-red-300">
                          <Zap className="h-2.5 w-2.5" /> SPIKE
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 pl-2 text-right font-mono text-[10px] text-gray-600">
                      {t.wallet ? `${t.wallet.slice(0, 6)}…` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
