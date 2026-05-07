// ---- Generate ----

export type CompactionMode = 'full' | 'viewpoint' | 'abstraction';

export type OutputFormat = 'mermaid' | 'plantuml' | 'exchange_xml' | 'json';

export interface GenerateRequest {
  query: string;
  formats: OutputFormat[];
  compaction: CompactionMode;
  viewpoint: string | null;
}

export interface Violation {
  rule: string;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export interface GenerateResponse {
  model_name: string;
  valid: boolean;
  best_effort: boolean;
  attempts: number;
  warning?: string;
  violations: Violation[];
  outputs: Partial<Record<OutputFormat, string>>;
}

// ---- Viewpoints ----

export interface ViewpointsResponse {
  viewpoints: Record<string, string>;
}

// ---- Admin / API keys ----

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  active: boolean;
  created_at: string;
  use_count: number;
  last_used: string | null;
}

export interface ListKeysResponse {
  keys: ApiKey[];
}

export interface CreateKeyRequest {
  name: string;
}

export interface CreateKeyResponse {
  id: string;
  name: string;
  key: string;
  prefix: string;
  created_at: string;
}
