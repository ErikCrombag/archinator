import { useState, useCallback } from 'react';
import { getStoredApiKey, setStoredApiKey } from '../api';

export function useApiKey() {
  const [apiKey, setApiKeyState] = useState<string>(() => getStoredApiKey());

  const setApiKey = useCallback((key: string) => {
    setStoredApiKey(key);
    setApiKeyState(key);
  }, []);

  const hasKey = apiKey.trim().length > 0;

  const maskedKey = hasKey
    ? `${apiKey.slice(0, 8)}...`
    : 'No key set';

  return { apiKey, setApiKey, hasKey, maskedKey };
}
