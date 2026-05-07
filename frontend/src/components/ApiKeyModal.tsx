import React, { useState } from 'react';

interface ApiKeyModalProps {
  onSave: (key: string) => void;
  onClose?: () => void;
  /** When true the modal cannot be dismissed without providing a key */
  required?: boolean;
}

export function ApiKeyModal({ onSave, onClose, required = false }: ApiKeyModalProps) {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError('Please enter an API key.');
      return;
    }
    onSave(trimmed);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg border border-gray-700 bg-gray-800 p-6 shadow-2xl">
        <h2 className="mb-1 text-xl font-semibold text-gray-100">
          API Key Required
        </h2>
        <p className="mb-5 text-sm text-gray-400">
          Enter your Archinator API key. It will be stored in localStorage and
          sent with every request.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium uppercase tracking-wider text-gray-400">
              API Key
            </label>
            <input
              type="password"
              autoFocus
              value={value}
              onChange={(e) => {
                setValue(e.target.value);
                setError('');
              }}
              placeholder="arch_..."
              className="w-full rounded border border-gray-600 bg-gray-900 px-3 py-2 font-mono text-sm text-gray-100 placeholder-gray-600 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            {error && (
              <p className="mt-1 text-xs text-red-400">{error}</p>
            )}
          </div>

          <div className="flex items-center justify-end gap-3">
            {onClose && !required && (
              <button
                type="button"
                onClick={onClose}
                className="rounded px-4 py-2 text-sm text-gray-400 hover:text-gray-200"
              >
                Cancel
              </button>
            )}
            <button
              type="submit"
              className="rounded bg-indigo-600 px-5 py-2 text-sm font-medium text-white hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800"
            >
              Save Key
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
