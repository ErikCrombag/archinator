import { useState } from 'react';
import type { GenerateResponse, OutputFormat } from '../types';
import { ViolationList } from './ViolationList';
import { OutputViewer } from './OutputViewer';

interface ResultPanelProps {
  result: GenerateResponse;
}

export function ResultPanel({ result }: ResultPanelProps) {
  const availableFormats = Object.keys(result.outputs) as OutputFormat[];
  const [activeTab, setActiveTab] = useState<OutputFormat>(
    availableFormats[0] ?? 'mermaid',
  );

  const formatLabels: Partial<Record<OutputFormat, string>> = {
    mermaid: 'Mermaid',
    plantuml: 'PlantUML',
    exchange_xml: 'Exchange XML',
    json: 'JSON',
  };

  return (
    <div className="space-y-5">
      {/* Best-effort banner */}
      {result.best_effort && (
        <div className="flex items-start gap-3 rounded border border-red-600 bg-red-950/60 px-4 py-3">
          <span className="mt-0.5 text-lg leading-none text-red-400">⚠</span>
          <div>
            <p className="font-semibold text-red-300">
              Best-effort result — diagram contains violations
            </p>
            {result.warning && (
              <p className="mt-1 text-sm text-red-400">{result.warning}</p>
            )}
          </div>
        </div>
      )}

      {/* Status badges */}
      <div className="flex flex-wrap items-center gap-3">
        {result.valid ? (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-green-700 bg-green-950/60 px-3 py-1 text-xs font-semibold text-green-400">
            <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
            Valid ArchiMate 3.2
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-red-700 bg-red-950/60 px-3 py-1 text-xs font-semibold text-red-400">
            <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
            Invalid
          </span>
        )}
        <span className="text-xs text-gray-500">
          Model: <span className="text-gray-300">{result.model_name}</span>
        </span>
        <span className="text-xs text-gray-500">
          Attempts: <span className="text-gray-300">{result.attempts}</span>
        </span>
      </div>

      {/* Violations */}
      {result.violations.length > 0 && (
        <ViolationList violations={result.violations} />
      )}

      {/* Output tabs */}
      {availableFormats.length > 0 && (
        <div>
          <div className="flex border-b border-gray-700">
            {availableFormats.map((fmt) => (
              <button
                key={fmt}
                onClick={() => setActiveTab(fmt)}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  activeTab === fmt
                    ? 'border-b-2 border-indigo-500 text-indigo-400'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {formatLabels[fmt] ?? fmt}
              </button>
            ))}
          </div>

          <div className="mt-4">
            {availableFormats.map((fmt) => {
              const content = result.outputs[fmt];
              if (!content || fmt !== activeTab) return null;
              return (
                <OutputViewer key={fmt} format={fmt} content={content} />
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
