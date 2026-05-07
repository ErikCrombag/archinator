import { useState } from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { GeneratorPage } from './pages/GeneratorPage';
import { AdminPage } from './pages/AdminPage';
import { ApiKeyModal } from './components/ApiKeyModal';
import { useApiKey } from './hooks/useApiKey';

export function App() {
  const { hasKey, maskedKey, setApiKey } = useApiKey();
  const [showKeyModal, setShowKeyModal] = useState(!hasKey);
  const location = useLocation();

  function handleSaveKey(key: string) {
    setApiKey(key);
    setShowKeyModal(false);
  }

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Top navigation */}
      <header className="sticky top-0 z-40 border-b border-gray-700 bg-gray-900/95 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
          {/* Logo / title */}
          <Link
            to="/"
            className="flex items-center gap-2 text-lg font-bold tracking-tight text-gray-100 hover:text-white"
          >
            <span className="font-mono text-indigo-400">▦</span>
            Archinator
          </Link>

          {/* Right side */}
          <div className="flex items-center gap-4">
            {/* Admin link */}
            <Link
              to="/admin"
              className={`text-sm transition-colors ${
                location.pathname === '/admin'
                  ? 'font-semibold text-indigo-400'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
            >
              Admin
            </Link>

            {/* API key indicator */}
            <button
              onClick={() => setShowKeyModal(true)}
              title="Click to change API key"
              className={`flex items-center gap-1.5 rounded border px-3 py-1.5 font-mono text-xs transition-colors ${
                hasKey
                  ? 'border-green-800 bg-green-950/40 text-green-400 hover:border-green-600'
                  : 'border-red-800 bg-red-950/40 text-red-400 hover:border-red-600 animate-pulse'
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${hasKey ? 'bg-green-400' : 'bg-red-400'}`}
              />
              {maskedKey}
            </button>
          </div>
        </div>
      </header>

      {/* Page content */}
      <main>
        <Routes>
          <Route path="/" element={<GeneratorPage />} />
          <Route path="/admin" element={<AdminPage />} />
        </Routes>
      </main>

      {/* API key modal */}
      {showKeyModal && (
        <ApiKeyModal
          onSave={handleSaveKey}
          onClose={hasKey ? () => setShowKeyModal(false) : undefined}
          required={!hasKey}
        />
      )}
    </div>
  );
}
