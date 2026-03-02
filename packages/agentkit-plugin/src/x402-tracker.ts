let paymentTxHashes: string[] = [];
let installed = false;

export function installX402Tracker(): void {
  if (installed) return;
  const originalFetch = globalThis.fetch;

  globalThis.fetch = async (...args: Parameters<typeof fetch>): Promise<Response> => {
    const response = await originalFetch(...args);

    const receipt = response.headers.get("x-payment-receipt");
    if (receipt && /^0x[a-fA-F0-9]{64}$/.test(receipt)) {
      paymentTxHashes.push(receipt);
      console.log(`[x402] Captured payment tx: ${receipt.slice(0, 14)}...`);
      return response;
    }

    const paymentHeader = response.headers.get("payment-response");
    if (paymentHeader) {
      try {
        const decoded = JSON.parse(atob(paymentHeader));
        const txHash = decoded.transaction ?? decoded.txHash;
        if (txHash && typeof txHash === "string") {
          paymentTxHashes.push(txHash);
          console.log(`[x402] Captured payment tx: ${txHash.slice(0, 14)}...`);
        }
      } catch {
        console.warn("[x402] Failed to decode payment-response header");
      }
    }

    return response;
  };

  installed = true;
  console.log("[x402] Fetch interceptor installed");
}

export function drainX402TxHashes(): string[] {
  const hashes = [...paymentTxHashes];
  paymentTxHashes = [];
  return hashes;
}
