import React, { useEffect, useState } from 'react';
import { listApiKeys, createApiKey, revokeApiKey, fetchMcpTools } from '../api';
import { API_URL } from '../config';
import type { ApiKey, CreateKeyResponse, McpTool } from '../types';

const OUTPUT_DESCRIPTIONS: Record<string, string> = {
  generate_diagram:
    'JSON — model_name, valid, violations[], compaction, outputs{format→string}. With compaction: compact_valid, compact_violations[].',
  validate_diagram:
    'JSON — valid (boolean), violations[] each with rule, message, severity, element_id, relationship_id.',
  query_spec:
    'Plain text — relevant spec excerpts separated by "---".',
  list_formats:
    'Plain text — bullet list of format names and descriptions.',
};

function McpSchemaSection({ tools, apiUrl }: { tools: McpTool[]; apiUrl: string }) {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-100">MCP Server</h1>
        <p className="mt-1 text-sm text-gray-400">
          Available tools and connection details for MCP clients (Claude Desktop, etc.).
        </p>
      </div>

      {/* Endpoints */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">Endpoints</h2>
        <div className="space-y-3">
          <div>
            <p className="mb-1 text-xs font-medium text-gray-400">HTTP / SSE (MCP over HTTP)</p>
            <code className="block rounded border border-gray-700 bg-gray-950 px-3 py-2 font-mono text-sm text-green-300">
              {apiUrl}/mcp
            </code>
            <p className="mt-1 text-xs text-gray-500">
              SSE connection: <span className="font-mono">GET {apiUrl}/mcp</span> — requires <span className="font-mono">X-API-Key</span> header.
              Messages: <span className="font-mono">POST {apiUrl}/mcp/messages/</span>
            </p>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-gray-400">stdio (Claude Desktop / local)</p>
            <code className="block rounded border border-gray-700 bg-gray-950 px-3 py-2 font-mono text-sm text-green-300">
              archinator-server
            </code>
          </div>
        </div>
      </div>

      {/* Tool cards */}
      {tools.map((tool) => {
        const props = tool.inputSchema.properties ?? {};
        const required = new Set(tool.inputSchema.required ?? []);
        const entries = Object.entries(props);
        const outputDesc = OUTPUT_DESCRIPTIONS[tool.name] ?? '—';
        return (
          <div key={tool.name} className="rounded-lg border border-gray-700 bg-gray-800/50">
            <div className="border-b border-gray-700 px-6 py-4">
              <h3 className="font-mono text-sm font-semibold text-indigo-300">{tool.name}</h3>
              <p className="mt-1 text-sm text-gray-300">{tool.description}</p>
            </div>

            {entries.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-700 text-xs font-medium uppercase tracking-wider text-gray-500">
                      <th className="px-6 py-3 text-left">Parameter</th>
                      <th className="px-6 py-3 text-left">Type</th>
                      <th className="px-6 py-3 text-left">Required</th>
                      <th className="px-6 py-3 text-left">Default</th>
                      <th className="px-6 py-3 text-left">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700/50">
                    {entries.map(([name, param]) => {
                      const typeLabel =
                        param.type === 'array' && param.items
                          ? `${param.type}<${param.items.enum ? param.items.enum.join(' | ') : param.items.type}>`
                          : param.enum
                          ? param.enum.join(' | ')
                          : param.type;
                      const defaultVal =
                        param.default !== undefined ? String(param.default) : '—';
                      return (
                        <tr key={name} className="hover:bg-gray-700/20">
                          <td className="px-6 py-3 font-mono text-xs text-indigo-200">{name}</td>
                          <td className="px-6 py-3 font-mono text-xs text-amber-300">{typeLabel}</td>
                          <td className="px-6 py-3 text-xs">
                            {required.has(name) ? (
                              <span className="text-red-400">yes</span>
                            ) : (
                              <span className="text-gray-500">no</span>
                            )}
                          </td>
                          <td className="px-6 py-3 font-mono text-xs text-gray-400">{defaultVal}</td>
                          <td className="px-6 py-3 text-xs text-gray-300">{param.description ?? '—'}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="border-t border-gray-700 px-6 py-3">
              <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Output</span>
              <p className="mt-1 text-xs text-gray-300">{outputDesc}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function AdminPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loadError, setLoadError] = useState('');
  const [newKeyName, setNewKeyName] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');
  const [newKeyResponse, setNewKeyResponse] = useState<CreateKeyResponse | null>(null);
  const [copied, setCopied] = useState(false);
  const [revokeConfirm, setRevokeConfirm] = useState<string | null>(null);
  const [revokeError, setRevokeError] = useState('');
  const [mcpTools, setMcpTools] = useState<McpTool[]>([]);

  async function loadKeys() {
    setLoadError('');
    try {
      const res = await listApiKeys();
      setKeys(res.keys);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : 'Failed to load keys.');
    }
  }

  useEffect(() => {
    loadKeys();
    fetchMcpTools().then((r) => setMcpTools(r.tools)).catch(() => {});
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newKeyName.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await createApiKey({ name: newKeyName.trim() });
      setNewKeyResponse(res);
      setNewKeyName('');
      await loadKeys();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create key.');
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: string) {
    setRevokeError('');
    try {
      await revokeApiKey(id);
      setRevokeConfirm(null);
      await loadKeys();
    } catch (err) {
      setRevokeError(err instanceof Error ? err.message : 'Failed to revoke key.');
    }
  }

  function handleCopyNewKey() {
    if (!newKeyResponse) return;
    navigator.clipboard.writeText(newKeyResponse.key).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function formatDate(iso: string | null) {
    if (!iso) return '—';
    return new Date(iso).toLocaleString();
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8 px-4 py-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-gray-100">
          API Key Management
        </h1>
        <p className="mt-1 text-sm text-gray-400">
          Create and revoke API keys used to access the Archinator backend.
        </p>
      </div>

      {/* Create key form */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-widest text-gray-400">
          Create New Key
        </h2>
        <form onSubmit={handleCreate} className="flex items-end gap-3">
          <div className="flex-1">
            <label className="mb-1.5 block text-xs font-medium text-gray-400">
              Key Name
            </label>
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="e.g. frontend-prod"
              required
              className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-100 placeholder-gray-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
          </div>
          <button
            type="submit"
            disabled={creating || !newKeyName.trim()}
            className="rounded bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {creating ? 'Creating…' : 'Create Key'}
          </button>
        </form>
        {createError && (
          <p className="mt-2 text-xs text-red-400">{createError}</p>
        )}
      </div>

      {/* Keys table */}
      <div className="rounded-lg border border-gray-700 bg-gray-800/50">
        <div className="border-b border-gray-700 px-6 py-4">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-gray-400">
            Existing Keys
          </h2>
        </div>

        {loadError ? (
          <div className="px-6 py-4 text-sm text-red-400">{loadError}</div>
        ) : keys.length === 0 ? (
          <div className="px-6 py-6 text-center text-sm text-gray-500">
            No API keys found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-xs font-medium uppercase tracking-wider text-gray-500">
                  <th className="px-6 py-3 text-left">Name</th>
                  <th className="px-6 py-3 text-left">Prefix</th>
                  <th className="px-6 py-3 text-left">Status</th>
                  <th className="px-6 py-3 text-left">Created</th>
                  <th className="px-6 py-3 text-right">Uses</th>
                  <th className="px-6 py-3 text-left">Last Used</th>
                  <th className="px-6 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700/50">
                {keys.map((key) => (
                  <tr key={key.id} className="hover:bg-gray-700/20">
                    <td className="px-6 py-3 font-medium text-gray-200">
                      {key.name}
                    </td>
                    <td className="px-6 py-3 font-mono text-xs text-gray-400">
                      {key.prefix}…
                    </td>
                    <td className="px-6 py-3">
                      {key.active ? (
                        <span className="inline-flex items-center gap-1 text-xs text-green-400">
                          <span className="h-1.5 w-1.5 rounded-full bg-green-400" />
                          Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                          <span className="h-1.5 w-1.5 rounded-full bg-gray-500" />
                          Revoked
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-400">
                      {formatDate(key.created_at)}
                    </td>
                    <td className="px-6 py-3 text-right tabular-nums text-gray-300">
                      {key.use_count}
                    </td>
                    <td className="px-6 py-3 text-xs text-gray-400">
                      {formatDate(key.last_used)}
                    </td>
                    <td className="px-6 py-3 text-right">
                      {key.active && (
                        <>
                          {revokeConfirm === key.id ? (
                            <span className="inline-flex items-center gap-2">
                              <span className="text-xs text-gray-400">Confirm?</span>
                              <button
                                onClick={() => handleRevoke(key.id)}
                                className="text-xs font-semibold text-red-400 hover:text-red-300"
                              >
                                Yes, revoke
                              </button>
                              <button
                                onClick={() => setRevokeConfirm(null)}
                                className="text-xs text-gray-500 hover:text-gray-300"
                              >
                                Cancel
                              </button>
                            </span>
                          ) : (
                            <button
                              onClick={() => setRevokeConfirm(key.id)}
                              className="text-xs font-semibold text-red-500 hover:text-red-400 transition-colors"
                            >
                              Revoke
                            </button>
                          )}
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {revokeError && (
          <div className="border-t border-gray-700 px-6 py-3 text-xs text-red-400">
            {revokeError}
          </div>
        )}
      </div>

      {/* MCP schema */}
      {mcpTools.length > 0 && (
        <McpSchemaSection tools={mcpTools} apiUrl={API_URL} />
      )}

      {/* One-time new key modal */}
      {newKeyResponse && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-lg border border-yellow-700 bg-gray-800 p-6 shadow-2xl">
            <h2 className="mb-1 text-xl font-semibold text-yellow-300">
              Save Your New API Key
            </h2>
            <p className="mb-5 text-sm text-yellow-400/80">
              This key will not be shown again. Copy it now and store it
              securely.
            </p>

            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-gray-400">
                Key Name
              </label>
              <p className="text-sm text-gray-200">{newKeyResponse.name}</p>
            </div>

            <div className="mb-6">
              <label className="mb-1.5 block text-xs font-medium text-gray-400">
                Raw API Key
              </label>
              <div className="flex items-center gap-2">
                <code className="flex-1 select-all overflow-auto rounded border border-gray-700 bg-gray-950 px-3 py-2 font-mono text-sm text-green-300 break-all">
                  {newKeyResponse.key}
                </code>
                <button
                  onClick={handleCopyNewKey}
                  className="shrink-0 rounded bg-gray-700 px-3 py-2 text-xs font-medium text-gray-300 hover:bg-gray-600 hover:text-white transition-colors"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <button
                onClick={() => {
                  setNewKeyResponse(null);
                  setCopied(false);
                }}
                className="rounded bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
              >
                I've saved the key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
