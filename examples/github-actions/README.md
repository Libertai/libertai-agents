# Deploying LibertAI Agents with GitHub Actions

This example shows how to set up Continuous Deployment for your LibertAI agent to Aleph Cloud.

## Quick Start

1. **Create an Aleph wallet**
   ```bash
   aleph account create
   # Save the private key securely
   ```

2. **Add the private key to GitHub Secrets**
   - Go to your repo → Settings → Secrets → Actions
   - Create a new secret named `ALEPH_PRIVATE_KEY`
   - Paste your private key (hex format, with or without 0x prefix)

3. **Copy the workflow file**
   ```bash
   mkdir -p .github/workflows
   cp examples/github-actions/deploy.yml .github/workflows/
   ```

4. **Push to deploy**
   ```bash
   git add .github/workflows/deploy.yml
   git commit -m "Add Aleph deployment workflow"
   git push
   ```

## What the Workflow Does

1. **Builds** your agent code into a squashfs archive
2. **Uploads** the archive to Aleph's decentralized storage
3. **Deploys** it as a serverless program on Aleph Cloud

## Customization

### Change the entrypoint

If your main app is in a different file or has a different name:

```yaml
aleph program upload /tmp/agent.squashfs your_module:your_app \
  --name "my-agent"
```

### Add environment variables

For API keys and configuration:

```yaml
env:
  ALEPH_PRIVATE_KEY: ${{ secrets.ALEPH_PRIVATE_KEY }}
  MY_API_KEY: ${{ secrets.MY_API_KEY }}
```

### Deploy as an instance (VM) instead of program

For persistent agents that need to run continuously:

```yaml
aleph instance create \
  --payment-type=credit \
  --name="my-agent" \
  --rootfs=ubuntu22 \
  --compute-units=1
```

## Monitoring Your Deployment

After deployment, you can:

- **View logs**: `aleph program logs <program-hash>`
- **Check status**: Visit `https://explorer.aleph.im`
- **Call your agent**: `https://api1.aleph.im/vm/<program-hash>`

## Troubleshooting

### "Insufficient funds" error
Make sure your wallet has credits. Get them at https://account.aleph.im

### Build failures
Check that all dependencies are listed in your requirements.txt or pyproject.toml.

## See Also

- [Aleph Cloud Docs](https://docs.aleph.cloud)
- [LibertAI Agents Docs](https://docs.libertai.io)
- [aleph-deploy-action](https://github.com/shem-aleph/aleph-deploy-action) - Reusable GitHub Action
