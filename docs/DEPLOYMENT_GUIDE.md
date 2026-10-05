# PRAMANA: simple free demo deployment

This guide runs the real app on a server, independently of your Mac. The demo is public: judges can query, resume shared history and use case files without entering a key. Ollama still runs the two specified Qwen models on the server; no cloud LLM or mock answer provider is introduced.

## Hosting choice

Use an eligible **Oracle Cloud Always Free ARM VM**. Current [Oracle limits](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) describe 2 OCPUs, 12 GB RAM and 200 GB of combined boot/block storage in the home region. Choose `VM.Standard.A1.Flex`, Ubuntu 24.04, 2 OCPUs, 12 GB RAM and a 50 GB boot volume, within your account's free allocation. Capacity is not guaranteed, and Oracle may reclaim idle instances. Confirm the console shows the resources as free before creating them.

This is a free server option, but it needs a one-time VM setup. Vercel's [function limits](https://vercel.com/docs/functions/limitations) do not fit this full Ollama/verification stack. [Hugging Face's current rules](https://huggingface.co/docs/hub/spaces-overview) require a paid plan for new Docker Spaces; their CPU Basic hourly price alone does not establish free eligibility. Railway is a paid alternative, outside the user's free-only budget.

No public server, domain or judging link has been provisioned yet.

## What gets deployed

```text
Judge's browser -> server port 80 -> production React frontend + Nginx
                                  -> FastAPI /v1 routes
                                  -> CPU Ollama on internal loopback
                                  -> PostgreSQL + pgvector on private Docker network
```

The root `Dockerfile` builds the actual frontend, backend and official CPU Ollama. `docker-compose.demo.yml` starts this web image and PostgreSQL. App memory is capped at 9 GiB and database memory at 768 MiB; app CPU is capped at two cores. Ollama loads one model at a time and uses two CPU threads for generation and embeddings. These limits constrain resources; latency and capacity must still be checked on the chosen server.

The Mac's original `docker-compose.yml` remains its local workflow. Do not use it on the server: it expects native Mac Ollama.

## 1. Prepare the actual code and corpus

Push the reviewed project changes to your GitHub repository before cloning on the server. New deployment files must be included; `.env`, `.env.deploy`, `deploy/data`, backups, models and generated dumps stay out of Git.

On the Mac, with the existing database running:

```bash
.venv/bin/python scripts/export-demo-seed.py
```

This creates `backups/demo-seed.tar.gz` containing real corpus rows, source PDFs, reference data and the measured evaluation report. It excludes conversations, saved results, escalation contacts, query records and audit payloads. Corpus statuses and reviews are preserved: staged data is not promoted. This archive is about 160 MB for the current corpus and is not committed to Git.

## 2. Create the free server

Create the eligible VM above with a public IPv4 address. Save the SSH key supplied during setup. Permit incoming TCP port **80** in the instance's Oracle network security rules and host firewall; SSH uses port 22. Follow Oracle's [Linux instance tutorial](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/launchinginstance.htm) for account-specific networking and connection steps.

Install Docker Engine and its Compose plugin using the [official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/). The commands below use `sudo` for Docker so no additional Linux group setup is necessary.

## 3. Copy the project and source data

SSH into the VM and clone the branch containing your deployment changes:

```bash
git clone https://github.com/sarthakv162/PRAMANA-SIH.git PRAMANA
cd PRAMANA
git checkout codex/free-demo-deployment
mkdir -p backups
```

`codex/free-demo-deployment` contains the completed demo implementation and deployment setup; use its latest reviewed commit. These commands require that the updated branch is available remotely. For a private repository, use your normal GitHub authentication.

From the Mac, transfer the archive using your actual key and VM IP:

```bash
scp -i /path/to/your-key backups/demo-seed.tar.gz ubuntu@YOUR_SERVER_IP:/home/ubuntu/PRAMANA/backups/demo-seed.tar.gz
```

The key path and IP are placeholders, not provisioned credentials or an existing server.

## 4. Start the demo

On the server, from the repository root:

```bash
bash deploy/setup-demo.sh
sudo docker compose --env-file .env.deploy -p pramana-demo -f docker-compose.demo.yml up -d --build
sudo docker compose --env-file .env.deploy -p pramana-demo -f docker-compose.demo.yml logs -f app
```

Setup generates a real random database password and copies the source archive into `deploy/data`. Startup provisions existing application roles, runs migrations, imports the real seed only if the corpus is empty, checks source PDF hashes, downloads the Qwen models, warms the verifier and starts the real API. Source checks run weekly and require the existing quality/review flow before promotion.

The first start downloads model files and may take several minutes. Once the logs show the app listening, check:

```bash
curl --fail http://127.0.0.1/v1/health
```

Expect `mock_mode: false`, `public_demo_mode: true`, actual model readiness and a real corpus version. An empty or failed import must not be presented as a working corpus. The current live corpus still has legacy embeddings, so `corpus_embedding_compatible` is false and retrieval uses its real keyword path. The staged Qwen corpus has outstanding quality issues and is not automatically promoted.

If you have a Sarvam key, put it in `SARVAM_API_KEY` inside `.env.deploy`, then recreate the app service. Hosting is free; Sarvam account limits and speech charges are separate. Without a key, read-aloud reports unavailable. No key is bundled into browser JavaScript.

## 5. Submit and test the public link

Open **`http://YOUR_SERVER_IP/`** from another device. This is the simple public prototype link after a real server has been created. It uses HTTP; add your existing domain and HTTPS separately if the judging rules require HTTPS. Do not submit localhost or the placeholder IP.

Check these real flows before judging:

1. Health and the UI show Live API, not fixture mode.
2. Ask “Summarize section 3(p) of the Patents Act and its introductory section.” Confirm verified claims, supporting citations and a valid receipt.
3. Open a citation. The actual PDF, bundled PDF worker and cited-page highlight must load.
4. Reload, resume the saved conversation, add its result to the case file and export a dossier. Another browser shares the same history without a key.
5. Delete a disposable conversation. Check an out-of-domain query and an in-scope missing source produce distinct, honest results.
6. Restart the app service and repeat the saved-history and case-file checks. Data lives in `deploy/data` and the database volume.
7. Exercise classification, patent, ABS, TK and evaluation screens using the detailed `USER_TEST_GUIDE.md`.
8. Test Sarvam playback if configured; unavailable speech must remain a visible error.

The existing biodiversity PDF fails its old stored hash in two corpus-version records. The viewer now returns `pdf_unavailable` for those records. Other tested citations remain usable. The original pinned PDF must be recovered or a corrected candidate reviewed before that source's PDF viewing can be accepted.

## Updating and troubleshooting

After a code push, run `git pull` and repeat the Compose `up -d --build` command on the VM. Keep the persistent data directory and database volume. Never delete volumes to perform a routine update.

Use `docker compose ... ps` and `logs app` for startup failures. An unavailable `vector` extension means the database image is wrong: use the supplied pgvector image. A model-download failure needs working outbound HTTPS and free disk space. A page that opens locally but not remotely usually needs port 80 opened in both the Oracle network rules and the VM firewall.

The local container verification script is `DEMO_BROWSER_CHECK=1 .venv/bin/python scripts/check-demo-container.py`; it uses an isolated database and real models/corpus, temporarily restarts the Mac API to conserve memory, and restores it afterward. This verifies the image locally, not Oracle account eligibility, regional availability, cloud latency or an external judging URL.

## Latest local image check

On 5 October 2026, the isolated two-core container produced a verified supported answer in 71.96 seconds, verified its receipt, served its matching PDF, and retained history/case references after restart. The public production browser test passed with real PDF highlighting and no workspace key. The screenshot was inspected. This does not establish Oracle-host speed or provision a public link.
