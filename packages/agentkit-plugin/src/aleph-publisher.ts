import { AuthenticatedAlephHttpClient } from "@aleph-sdk/client";
import { importAccountFromPrivateKey } from "@aleph-sdk/ethereum";
import { ItemType } from "@aleph-sdk/message";
import type { ActivityType, AgentActivity } from "./types.js";

export class AlephPublisher {
  private client: AuthenticatedAlephHttpClient | null = null;
  private channel: string;

  constructor(
    private privateKey: string,
    channel?: string,
  ) {
    this.channel = channel ?? "libertai";
  }

  async init(): Promise<void> {
    try {
      const account = importAccountFromPrivateKey(this.privateKey);
      this.client = new AuthenticatedAlephHttpClient(account);
      console.log("[aleph] Publisher initialized");
    } catch (err) {
      console.error("[aleph] Failed to init publisher:", err);
    }
  }

  async publish(postType: ActivityType, activity: AgentActivity): Promise<void> {
    if (!this.client) {
      console.warn("[aleph] Publisher not initialized, skipping publish");
      return;
    }
    try {
      await this.client.createPost({
        postType,
        content: activity,
        channel: this.channel,
        storageEngine: ItemType.inline,
      });
      console.log(`[aleph] Published ${postType}`);
    } catch (err) {
      console.error(`[aleph] Failed to publish ${postType}:`, err);
    }
  }
}
