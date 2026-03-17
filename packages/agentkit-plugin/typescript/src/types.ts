export interface ToolExecution {
  name: string;
  args?: Record<string, string>;
  result?: string;
  txHash?: string;
  meta?: Record<string, string>;
}

export type ActivityType = "inventory" | "survival" | "strategy" | "error";

export interface AgentActivity {
  summary: string;
  model: string;
  cycleId: string;
  tools?: ToolExecution[];
  txHashes?: string[];
}
