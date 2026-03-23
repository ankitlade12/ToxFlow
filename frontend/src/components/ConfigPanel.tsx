import { useState } from "react";
import { Play, BarChart3, Loader2 } from "lucide-react";

interface Props {
  onRunSingle: (params: ConfigParams) => void;
  onRunMonteCarlo: (params: ConfigParams & { simulations: number }) => void;
  loading: boolean;
}

export interface ConfigParams {
  duration: number;
  bucketVolume: number;
  vpinWindow: number;
  zThreshold: number;
  capital: number;
  seed: number;
  useSynthesis: boolean;
}

export default function ConfigPanel({ onRunSingle, onRunMonteCarlo, loading }: Props) {
  const [duration, setDuration] = useState(3600);
  const [bucketVolume, setBucketVolume] = useState(100);
  const [vpinWindow, setVpinWindow] = useState(30);
  const [zThreshold, setZThreshold] = useState(0.5);
  const [capital, setCapital] = useState(10000);
  const [seed, setSeed] = useState(42);
  const [useSynthesis, setUseSynthesis] = useState(true);
  const [simulations, setSimulations] = useState(100);

  const params: ConfigParams = {
    duration,
    bucketVolume,
    vpinWindow,
    zThreshold,
    capital,
    seed,
    useSynthesis,
  };

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-lg p-4">
      <h3 className="text-sm font-medium text-gray-300 mb-4">Parameters</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <Field label="Duration (s)" value={duration} onChange={setDuration} />
        <Field label="Bucket Volume ($)" value={bucketVolume} onChange={setBucketVolume} />
        <Field label="VPIN Window" value={vpinWindow} onChange={setVpinWindow} />
        <Field label="Z-Threshold" value={zThreshold} onChange={setZThreshold} step={0.1} />
        <Field label="Capital ($)" value={capital} onChange={setCapital} />
        <Field label="Seed" value={seed} onChange={setSeed} />
        <Field label="MC Sims" value={simulations} onChange={setSimulations} />
        <div className="flex items-end">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={useSynthesis}
              onChange={(e) => setUseSynthesis(e.target.checked)}
              className="rounded bg-gray-700 border-gray-600"
            />
            <span className="text-xs text-gray-300">Synthesis AI</span>
          </label>
        </div>
      </div>

      <div className="flex gap-2">
        <button
          onClick={() => onRunSingle(params)}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
          Run Backtest
        </button>
        <button
          onClick={() => onRunMonteCarlo({ ...params, simulations })}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 text-white text-sm font-medium rounded-lg transition-colors"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <BarChart3 className="w-4 h-4" />}
          Monte Carlo
        </button>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  step,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full px-2 py-1.5 bg-gray-700/50 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-blue-500"
      />
    </div>
  );
}
