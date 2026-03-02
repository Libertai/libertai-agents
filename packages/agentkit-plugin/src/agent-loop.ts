import { LLMClient, type ChatMessage, type Tool } from "@blockrun/llm";
import { type Hex } from "viem";
import type { ToolExecution } from "./types.js";

export interface AgentLoopOptions {
  maxRounds?: number;
  extractTxHashes?: boolean;
}

export interface AgentLoopResult {
  response: string;
  toolExecutions: ToolExecution[];
  txHashes: string[];
}

export function createLLMClient(privateKey: Hex): LLMClient {
  return new LLMClient({ privateKey });
}

export async function runAgentLoop(
  client: LLMClient,
  model: string,
  systemPrompt: string,
  userPrompt: string,
  tools: Tool[],
  executeTool: (name: string, argsJson: string) => Promise<string>,
  options?: AgentLoopOptions,
): Promise<AgentLoopResult> {
  const maxRounds = options?.maxRounds ?? 10;
  const extractTxHashes = options?.extractTxHashes ?? true;

  const messages: ChatMessage[] = [
    { role: "system", content: systemPrompt },
    { role: "user", content: userPrompt },
  ];

  const toolExecutions: ToolExecution[] = [];
  const txHashes: string[] = [];

  for (let round = 0; round < maxRounds; round++) {
    const result = await client.chatCompletion(model, messages, {
      tools: tools.length > 0 ? tools : undefined,
      toolChoice: tools.length > 0 ? "auto" : undefined,
    });

    const choice = result.choices[0];
    const msg = choice.message;

    messages.push({
      role: "assistant",
      content: msg.content ?? null,
      tool_calls: msg.tool_calls,
    });

    if (choice.finish_reason !== "tool_calls" || !msg.tool_calls?.length) {
      return { response: msg.content ?? "", toolExecutions, txHashes };
    }

    for (const toolCall of msg.tool_calls) {
      const { name, arguments: argsJson } = toolCall.function;
      console.log(`[tool] calling ${name}(${argsJson})`);

      const toolResult = await executeTool(name, argsJson);
      console.log(`[tool] ${name} -> ${toolResult.slice(0, 200)}`);

      let args: Record<string, string> | undefined;
      try {
        args = JSON.parse(argsJson);
      } catch {
        args = undefined;
      }

      let txHash: string | undefined;
      if (extractTxHashes) {
        const matches = toolResult.matchAll(/[Hh]ash:?\s*(0x[a-fA-F0-9]{64})/g);
        for (const m of matches) {
          if (!txHash) txHash = m[1]; // first match for backward compat
          txHashes.push(m[1]);
        }
      }

      toolExecutions.push({ name, args, result: toolResult, txHash });

      messages.push({
        role: "tool",
        tool_call_id: toolCall.id,
        content: toolResult,
      });
    }
  }

  console.log("[llm] max tool rounds reached, getting final response");
  const final = await client.chatCompletion(model, messages);
  return { response: final.choices[0].message.content ?? "", toolExecutions, txHashes };
}
