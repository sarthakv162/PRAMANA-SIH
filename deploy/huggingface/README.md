---
title: PRAMANA
emoji: 🌿
colorFrom: green
colorTo: blue
sdk: gradio
sdk_version: 6.29.1
python_version: "3.12"
app_file: app.py
pinned: false
license: mit
---

# PRAMANA

Citation-grounded Ayurveda IP and regulatory research demo. Uses Qwen3 4B and
Qwen3 Embedding 0.6B on Hugging Face ZeroGPU, with server-side citation verification.

The website, retrieval, classification tools, receipts, PDF viewer, and temporary
history use the same implementation as the local application. No managed database
or paid disk is needed. History, case files, and receipts reset on restart; the
packaged live corpus is restored on each startup.

Choose **ZeroGPU** hardware in Space settings and set **GRADIO_SSR_MODE=false**.
SARVAM_API_KEY is an optional Space secret for speech. No cloud text-generation API
or Mac connection is used. The rejected staged corpus is excluded.

Free ZeroGPU hosting requires a verified personal account older than 30 days.
Visitors have daily GPU quotas and may queue. See the
[official ZeroGPU documentation](https://huggingface.co/docs/hub/spaces-zerogpu).
