import { type LLMClient } from "@blockrun/llm";
import type { ToolExecution } from "./types.js";

export async function summarizePhase(
  client: LLMClient,
  model: string,
  phaseType: string,
  reasoning: string,
  toolExecutions: ToolExecution[],
): Promise<string> {
  const toolSummary = toolExecutions
    .map((t) => {
      const name = t.name.replace(/^[A-Za-z]+Provider_/, "");
      return t.txHash ? `${name} (tx: ${t.txHash.slice(0, 10)}...)` : name;
    })
    .join(", ");

  const prompt = `Summarize this ${phaseType} phase in 1-2 short sentences. Focus on what was done and the outcome. No preamble.

Reasoning: ${reasoning.slice(0, 1000)}
${toolSummary ? `Tools called: ${toolSummary}` : "No tools called."}`;

  try {
    const result = await client.chatCompletion(model, [{ role: "user", content: prompt }]);
    return result.choices[0].message.content ?? reasoning.slice(0, 200);
  } catch (err) {
    console.warn(`[summarizer] Failed to summarize ${phaseType}:`, err);
    return reasoning.slice(0, 200);
  }
}
