import React, { useEffect, useState } from 'react';
import { fetchViewpoints } from '../api';
import type { CompactionMode, OutputFormat } from '../types';

interface QueryFormProps {
  onSubmit: (params: {
    query: string;
    formats: OutputFormat[];
    compaction: CompactionMode;
    viewpoint: string | null;
  }) => void;
  loading: boolean;
}

const ALL_FORMATS: OutputFormat[] = ['mermaid', 'plantuml', 'exchange_xml', 'json'];

const FORMAT_LABELS: Record<OutputFormat, string> = {
  mermaid: 'Mermaid',
  plantuml: 'PlantUML',
  exchange_xml: 'Exchange XML',
  json: 'JSON',
};

export function QueryForm({ onSubmit, loading }: QueryFormProps) {
  const [query, setQuery] = useState('');
  const [formats, setFormats] = useState<OutputFormat[]>(['mermaid']);
  const [compaction, setCompaction] = useState<CompactionMode>('full');
  const [viewpoint, setViewpoint] = useState<string>('none');
  const [viewpoints, setViewpoints] = useState<Record<string, string>>({});
  const [vpError, setVpError] = useState('');

  useEffect(() => {
    fetchViewpoints()
      .then((r) => setViewpoints(r.viewpoints))
      .catch(() => setVpError('Could not load viewpoints.'));
  }, []);

  function toggleFormat(fmt: OutputFormat) {
    setFormats((prev) =>
      prev.includes(fmt) ? prev.filter((f) => f !== fmt) : [...prev, fmt],
    );
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    if (formats.length === 0) return;
    onSubmit({
      query: query.trim(),
      formats,
      compaction,
      viewpoint: viewpoint === 'none' ? null : viewpoint,
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Query textarea */}
      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-widest text-gray-400">
          Diagram Query
        </label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={5}
          required
          placeholder="Describe the architecture you want to model, e.g. 'Generate an application layer diagram showing the order management microservice and its dependencies…'"
          className="w-full resize-y rounded border border-gray-700 bg-gray-950 px-4 py-3 font-mono text-sm text-gray-100 placeholder-gray-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
        />
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {/* Format checkboxes */}
        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gray-400">
            Output Formats
          </label>
          <div className="space-y-1.5">
            {ALL_FORMATS.map((fmt) => (
              <label
                key={fmt}
                className="flex cursor-pointer items-center gap-2 text-sm text-gray-300 hover:text-gray-100"
              >
                <input
                  type="checkbox"
                  checked={formats.includes(fmt)}
                  onChange={() => toggleFormat(fmt)}
                  className="h-4 w-4 rounded border-gray-600 bg-gray-800 accent-indigo-500"
                />
                {FORMAT_LABELS[fmt]}
              </label>
            ))}
          </div>
          {formats.length === 0 && (
            <p className="mt-1 text-xs text-red-400">
              Select at least one format.
            </p>
          )}
        </div>

        {/* Compaction radio */}
        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gray-400">
            Compaction
          </label>
          <div className="space-y-1.5">
            {(['full', 'viewpoint', 'abstraction'] as CompactionMode[]).map(
              (mode) => (
                <label
                  key={mode}
                  className="flex cursor-pointer items-center gap-2 text-sm text-gray-300 hover:text-gray-100"
                >
                  <input
                    type="radio"
                    name="compaction"
                    value={mode}
                    checked={compaction === mode}
                    onChange={() => setCompaction(mode)}
                    className="h-4 w-4 border-gray-600 bg-gray-800 accent-indigo-500"
                  />
                  <span className="capitalize">{mode}</span>
                </label>
              ),
            )}
          </div>
        </div>

        {/* Viewpoint dropdown */}
        <div>
          <label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-gray-400">
            Viewpoint
          </label>
          {vpError ? (
            <p className="text-xs text-red-400">{vpError}</p>
          ) : (
            <select
              value={viewpoint}
              onChange={(e) => setViewpoint(e.target.value)}
              className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            >
              <option value="none">None</option>
              {Object.keys(viewpoints).map((vp) => (
                <option key={vp} value={vp}>
                  {vp}
                </option>
              ))}
            </select>
          )}
          {viewpoint !== 'none' && viewpoints[viewpoint] && (
            <p className="mt-1.5 text-xs text-gray-500 leading-relaxed">
              {viewpoints[viewpoint]}
            </p>
          )}
        </div>
      </div>

      <button
        type="submit"
        disabled={loading || formats.length === 0 || !query.trim()}
        className="flex items-center gap-2 rounded bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-900"
      >
        {loading && (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
        )}
        {loading ? 'Generating…' : 'Generate Diagram'}
      </button>
    </form>
  );
}
