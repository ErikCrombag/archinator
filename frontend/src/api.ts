import { API_URL } from './config';
import type {
  GenerateRequest,
  GenerateResponse,
  ViewpointsResponse,
  ListKeysResponse,
  CreateKeyRequest,
  CreateKeyResponse,
  McpToolsResponse,
} from './types';

const API_KEY_STORAGE_KEY = 'archinator_api_key';

export function getStoredApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE_KEY) ?? '';
}

export function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? body.message ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json() as Promise<T>;
}

export async function generateDiagram(
  req: GenerateRequest,
): Promise<GenerateResponse> {
  return request<GenerateResponse>('/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function fetchViewpoints(): Promise<ViewpointsResponse> {
  return request<ViewpointsResponse>('/viewpoints');
}

export async function listApiKeys(): Promise<ListKeysResponse> {
  return request<ListKeysResponse>('/admin/keys');
}

export async function createApiKey(
  req: CreateKeyRequest,
): Promise<CreateKeyResponse> {
  return request<CreateKeyResponse>('/admin/keys', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function revokeApiKey(id: string): Promise<void> {
  return request<void>(`/admin/keys/${id}`, { method: 'DELETE' });
}

export async function fetchMcpTools(): Promise<McpToolsResponse> {
  return request<McpToolsResponse>('/mcp/tools');
}

export async function previewPlantuml(source: string): Promise<string> {
  const apiKey = getStoredApiKey();
  const res = await fetch(`${API_URL}/preview/plantuml`, {
    method: 'POST',
    headers: {
      'Content-Type': 'text/plain',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
    },
    body: source,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text.slice(0, 300)}`);
  }
  return res.text(); // SVG string
}
