import { useState } from 'react';
import { generateDiagram } from '../api';
import { QueryForm } from '../components/QueryForm';
import { ResultPanel } from '../components/ResultPanel';
import type { GenerateResponse, CompactionMode, OutputFormat } from '../types';

export function GeneratorPage() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [error, setError] = useState<string>('');

  async function handleSubmit(params: {
    query: string;
    formats: OutputFormat[];
    compaction: CompactionMode;
    viewpoint: string | null;
  }) {
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await generateDiagram(params);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-100">
          ArchiMate Diagram Generator
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Describe your architecture. The backend will generate a validated
          ArchiMate 3.2 diagram using your local Ollama model.
        </p>
      </div>

      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
        <QueryForm onSubmit={handleSubmit} loading={loading} />
      </div>

      {error && (
        <div className="rounded border border-red-700 bg-red-950/50 px-4 py-3 text-sm text-red-300">
          <span className="font-semibold">Error: </span>{error}
        </div>
      )}

      {result && (
        <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
          <h2 className="mb-5 text-sm font-semibold uppercase tracking-widest text-gray-400">
            Result
          </h2>
          <ResultPanel result={result} />
        </div>
      )}
    </div>
  );
}
