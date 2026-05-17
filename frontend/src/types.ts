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

// ---- MCP tools schema ----

export interface McpToolParam {
  type: string;
  description?: string;
  enum?: string[];
  default?: unknown;
  items?: { type: string; enum?: string[] };
}

export interface McpTool {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    required?: string[];
    properties: Record<string, McpToolParam>;
  };
}

export interface McpToolsResponse {
  tools: McpTool[];
}
