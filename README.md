<h1 align="center">LibertAI Agents</h1>

<img width="3000" height="1000" alt="image" src="https://github.com/user-attachments/assets/abbc096c-f675-4967-abaf-24d34d8f4095" />


Tools and integrations for building **self-sustaining AI agents** that pay for their own compute and inference.

## Packages

| Package             | TypeScript                                                                                                                | Python                                                                                                                | Description                                                                                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **x402**            | [![npm](https://img.shields.io/npm/v/@libertai/x402)](https://www.npmjs.com/package/@libertai/x402)                       | [![PyPI](https://img.shields.io/pypi/v/libertai-x402)](https://pypi.org/project/libertai-x402/)                       | HTTP client wrappers to use x402 with LibertAI products, compatible with the OpenAI SDK and any HTTP client.                                                   |
| **agentkit-plugin** | [![npm](https://img.shields.io/npm/v/@libertai/agentkit-plugin)](https://www.npmjs.com/package/@libertai/agentkit-plugin) | [![PyPI](https://img.shields.io/pypi/v/libertai-agentkit-plugin)](https://pypi.org/project/libertai-agentkit-plugin/) | [Coinbase AgentKit](https://github.com/coinbase/agentkit) with an x402-powered LLM client & decentralize compute powered by [Aleph Cloud](https://aleph.cloud) |

## Examples

Working examples of autonomous agents using the AgentKit integration:

- [TypeScript](examples/agentkit/typescript/)
- [Python](examples/agentkit/python/)

## Deployment

```sh
pip install libertai-client
libertai agentkit deploy ./my-agent
```

See the [deployment docs](https://docs.libertai.io/agents/deployment) for details.
