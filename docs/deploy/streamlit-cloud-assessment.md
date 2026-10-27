# Deploying CargoLint on Streamlit Community Cloud: assessment

Investigation of 2026-10-27 on `main` at `b03ee39`; the application code is unchanged since `a53142c`. Nothing in
the repository was changed and no paid call was made. Sizes
come from this machine's full build. Memory was measured with a local script (Windows 11, Python 3.13.14, Streamlit
1.65.0, chromadb 1.5.9) that opened a copy of `store/chroma`, never the store itself, and made no OpenRouter call.
Platform facts are quoted from the Community Cloud and OpenRouter documentation listed in §6.

## Verdict

- **A demo fits; the full build does not.** With the nomenclature index and a reduced ruling index the app needs about
  450–500 MB at rest and about 800 MB while a scanned PDF or photo is read. The full ruling index (73,899 rulings,
  1.8 GB on disk) would need about 1.9 GB and is too large for a plain Git repository.
- **A fresh clone cannot start.** `store/` is gitignored, and without `store/index_meta.json` the app stops with
  "Knowledge base problem". Six items must reach the cloud: `store/index_meta.json`, `store/bm25.pkl`, `store/chroma/`,
  a reduced `store/chroma-bti/` with its `store/bti_docs.jsonl`, and `data/taric.jsonl`.
- **Secrets need no code change.** Streamlit copies root-level secrets into `os.environ` before the app runs, and
  `agent/config.py` reads `os.environ`.
- **The demo store costs nothing to build.** All 192 demo rulings are in the local full index with identical embedded
  text, and the nomenclature index is the same in both builds, so a demo store can be cut from the local one without
  any embedding call.
- **Smallest change set**: a free script that cuts the demo store; one way of shipping it (recommended: a release
  archive downloaded at first start); a password gate of about 15 lines; a dedicated OpenRouter key with a credit
  limit; Python 3.13 chosen at deploy time.

## 1. What the app reads that a fresh clone lacks

### Read at start-up

`app.py:load_kb()` calls `rag/loader.py:open_knowledge_base()` once per server process (`st.cache_resource`).

| Path | How it is produced today | Size here | Without it |
|---|---|---|---|
| `store/index_meta.json` | `python -m rag.loader` (any mode), written last | 1 KB | **Stops cleanly**: `IndexMismatchError`, the page shows "Knowledge base problem: no index_meta.json in store — build the knowledge base with `python -m rag.loader`". Also stops when its `embedding_model` differs from `CARGOLINT_EMBED_MODEL`. |
| `store/bm25.pkl` | `python -m rag.loader`, from the tracked `data/nomenclature_2026.jsonl`, no API call | 4.9 MB | **Crashes**: uncaught `FileNotFoundError`. Community Cloud forces `showErrorDetails = false`, so visitors see a generic error. |
| `store/chroma/`, collection `cn2026` (5,612 HS-6 chunks × 4,096 dimensions) | `python -m rag.loader`, embeds the nomenclature through OpenRouter (`qwen/qwen3-embedding-8b`, about 1.7 M tokens, about $0.02) | 134 MB: SQLite 44 MB, vector index 92.7 MB, 1.6 MB | **Degrades silently** when `index_meta.json` exists: Chroma creates an empty database in its place, the vector leg finds nothing, and retrieval runs on BM25 and the precedent leg. |
| `store/bti_docs.jsonl` | `python -m rag.loader` copies `data/bti_demo.jsonl` (`--demo`, 192 rulings) or `data/bti_subset.jsonl` (full build, 73,899 rulings) | 0.3 MB demo, 97 MB full | **Degrades**: empty ruling store, no cited precedents. |
| `store/chroma-bti/`, collection `bti` (one vector per ruling) | `python -m rag.loader`, embeds the rulings (the full build, with the nomenclature: 25.4 M tokens, $0.27) | 1.8 GB full: SQLite 633 MB, vector index 1.22 GB. About 5–10 MB for 192 rulings (estimate) | **Degrades**: no precedent leg and no ruling vote at HS-6 or CN-8, so every gate falls back to the model's confidence (auto-accept at 85 or more). `open_knowledge_base` also treats an empty collection as absent. |
| `data/taric.jsonl` | `python -m rag.loader --taric` from the signed Swedish Customs files in `data/raw/taric/`; needs gpg | 29 MB, 2.0 MB gzipped | **Degrades**: `open_taric_store` logs the reason and returns `None`; digits 9–10 and measures show "TARIC not loaded". |

### Read at start-up or on first use, all tracked

`data/nomenclature_2026.jsonl` (5.2 MB, at start-up), `data/rules/*.json`, `data/shippers.json`,
`data/model_prices.json` (cost display), `data/samples/sample_packing_list.xlsx` (the sample button),
`tests/eval/cn8_eval_history.json` and `tests/eval/results.json` (Admin › Quality), and `.streamlit/config.toml`.

### Models and caches

- **Embeddings**: no local model. Lines and queries are embedded by OpenRouter at run time; the query vectors are
  cached in memory per process.
- **Chroma's default embedding model** (all-MiniLM, downloaded to `~/.cache/chroma` on first use): never used.
  `langchain_chroma` creates the collections with `embedding_function=None`.
- **OCR**: the three RapidOCR models (PP-OCRv6 detection 9.9 MB, recognition 21.2 MB, classifier 0.6 MB) ship inside
  the `rapidocr` 3.10.0 wheel, so nothing is downloaded. They load on the first scanned PDF or photo.
- No tiktoken, HuggingFace or NLTK cache is used.

### Absent from a clone but not read by the app

- `data/raw/` (1.4 GB): the loader's downloads (CN SKOS file, EBTI extract, ICS2 PDFs, TARIC files).
- `data/bti_subset.jsonl` (97 MB): the full build's intermediate file.
- `store/logs/` (69 KB): TARIC loader logs.
- `store/*.png`, `store/snap-detail.yml`: screenshots from UI checks.
- `.specify/feature.json` (62 bytes, ignored by `.specify/.gitignore`): Spec Kit's pointer to the active feature.
- `.env`, `.streamlit/secrets.toml`: local secrets, never committed.

## 2. Settings and secrets

`agent/config.py:load_settings()` calls `load_dotenv(ROOT / ".env", override=False)` and then reads `os.environ`;
`get_settings()` caches the result for the life of the process. The settings are:

- `OPENROUTER_API_KEY`, which is required: without it `app.py` shows "OPENROUTER_API_KEY is not set…" and stops;
- `OPENROUTER_HTTP_REFERER` and `OPENROUTER_APP_TITLE`;
- the model and build settings `CARGOLINT_CHAT_MODEL`, `CARGOLINT_EMBED_MODEL` (which must match the index) and
  `CARGOLINT_STRUCTURED_METHOD`;
- `CARGOLINT_USD_EUR`, `CARGOLINT_WORKERS` (default 6) and `CARGOLINT_OCR_MIN_SCORE`;
- the switches `CARGOLINT_REASONING`, `CARGOLINT_HS6_OVERRIDE` and `CARGOLINT_QUERY_EXPANSION`.

`CARGOLINT_GPG` is used by the TARIC loader only.

**`st.secrets` works as a drop-in, with no code change.** In Streamlit 1.65, `streamlit run` loads the secrets file
during server bootstrap (`streamlit/web/bootstrap.py:250`, `secrets.load_if_toml_exists()`), before any script runs. It
then copies every root-level secret whose value is a string, integer or float into `os.environ`
(`streamlit/runtime/secrets.py`, `_maybe_set_environment_variable`). Streamlit's documentation says the same: "the
root-level secrets are also accessible as environment variables". Community Cloud uses "the same secrets management
workflow as you would locally", with the values entered in the app's Secrets settings:

```toml
OPENROUTER_API_KEY = "sk-or-…"
CARGOLINT_WORKERS = "3"
```

Conditions:

- **Root level only**: keys under a `[section]` are not copied into the environment.
- **Strings for switches**: TOML booleans are not copied, so write `CARGOLINT_HS6_OVERRIDE = "off"`, not `false`.
- **Reboot after editing a secret**: the settings are cached per process, and so is the knowledge base, with its
  embeddings client (`st.cache_resource`).
- **New settings belong in `os.environ`, not `st.secrets`.** Without a secrets file, as on the development machine,
  any lookup through `st.secrets` raises `StreamlitSecretNotFoundError`. So a demo password should be read from the
  environment like every other setting.
- **Optional wording fix**: the missing-key message tells the reader to set an operating-system variable; on the cloud
  it should point to the app's Secrets.
- **Constitution**: "API keys MUST come from environment variables, never from the UI, and MUST NOT be committed" is
  still met. The key reaches the app as an environment variable, and it lives in the Cloud settings, not in the
  repository.

## 3. Memory

Measured stage by stage in one process. The figures are the Windows working set, the counterpart of resident memory
(RSS) on Linux.

| Stage | Working set | Added |
|---|---|---|
| Python | 26 MB | |
| `import streamlit` | 57 MB | +31 |
| `openai`, `langchain`, `langchain_openai`, `langgraph` | 113 MB | +55 |
| `chromadb`, `langchain_chroma` | 138 MB | +25, plus about 500 MB reserved but untouched |
| `numpy`, `pandas`, `openpyxl`, `pdfplumber`, `lxml`, `rank_bm25` | 197 MB | +59 |
| the app's own modules | 198 MB | +1 |
| nomenclature index (5,612 chunks) | 217 MB | +19 |
| Chroma `cn2026` opened (its vector index is loaded) | 322 MB | +104 |
| BM25 index | 373 MB | +50 |
| rule lists and shippers | 373 MB | +1 |
| ruling store, 192 demo rulings | 374 MB | +1 |
| TARIC snapshot | 402 MB | +28 |
| first vector query | 404 MB | +1 |
| OCR engine loaded (first scanned PDF or photo) | 417 MB | +14 |
| one OCR pass over the sample photo | 538 MB | +120 (peak 704 MB during the pass) |
| ruling store with all 73,899 rulings (for comparison) | 738 MB | +200 |

Two things were not measured: the Streamlit server with its sessions (estimate: a few tens of MB, plus each open
session's shipment) and a demo `chroma-bti` (192 vectors, about 3 MB of index). The full `chroma-bti` would add its
1.22 GB vector file at start-up, because `open_knowledge_base` calls `count()` on it.

Community Cloud documents "Memory: 690MB minimum, 2.7GBs maximum" as of February 2024, which "may change at any time
without notice". Your planning figure of about 1 GB sits between the two. Estimates (each ruling costs about 19 KB of
memory: 16.5 KB of vector index and 2.7 KB of record):

| Ruling index | At rest | Peak while reading a scan or photo | Fits in about 1 GB |
|---|---|---|---|
| 192 demo rulings | about 450–500 MB | about 800 MB | yes |
| 5,000 rulings | about 550–600 MB | about 900 MB | yes |
| 10,000 rulings | about 650–700 MB | about 1.0 GB | at the edge |
| 73,899 rulings (full build) | about 1.9 GB | about 2.2 GB | no |

What could be made lazy or dropped, in order of benefit:

1. **OCR**: it already loads only when needed, and it is the only large temporary cost (about +300 MB at the peak). For
   a demo, uploads could be limited to xlsx, csv and text PDFs: `SUPPORTED_FILE_KINDS` plus a guard on scanned PDFs.
   That removes the peak but also the photo demo.
2. **Fewer workers**: `CARGOLINT_WORKERS = "3"` halves the parallel classification threads, which suits the
   0.078–2 cores anyway. Configuration only.
3. **The agent chat**: the LangChain agent is imported with the Admin page. Importing it only when "Ask the agent"
   opens would save part of the 55 MB. Minor.
4. **TARIC** (28 MB): lazy loading, or a snapshot of the 12 target chapters (6.1 MB, 0.4 MB gzipped), would save
   22–28 MB. That is not worth the code or the lost coverage.
5. **Chroma for the nomenclature** (about 130 MB with its import): it could be replaced by a numpy matrix behind the
   existing `InMemoryVectorSearch` (46 MB in float16). That is a larger change and not needed for the app to fit.
6. **BM25** (50 MB): it could be switched off, but hybrid retrieval is constitution Principle IV. Keep it.

Caveat: these are Windows figures. Linux resident memory can differ by ±20 %, more with many threads.

## 4. The smallest set of changes

### 4.1 Common to every option

1. **A budget cap at the source.** Use a dedicated OpenRouter key for the demo with a credit limit. OpenRouter lets
   every key have a limit with an optional daily, weekly or monthly reset, and refuses requests once it is used up.
   That caps the spend even if the password leaks.
2. **A password gate**: about 15 lines in `app.py` and one setting. `agent/config.py` reads `CARGOLINT_APP_PASSWORD`
   from the environment. On the cloud it is a root-level secret; locally it is unset and the gate is off. The gate
   sits at the start of `main()`, before the key check and `load_kb()`, so a visitor without the password loads
   nothing and spends nothing. A sketch, not applied:

   ```python
   password = get_settings().app_password             # CARGOLINT_APP_PASSWORD; unset locally
   if password and not st.session_state.get("gate_ok"):
       entered = st.text_input("Password", type="password")
       if entered and hmac.compare_digest(entered.encode(), password.encode()):
           st.session_state["gate_ok"] = True
           st.rerun()
       if entered:
           st.error("Wrong password.")
       st.stop()
   ```

   Trade-off: one shared password, no identity and no lockout. The reference shipped with Streamlit calls such a gate
   "not authentication" and recommends `st.login`. Alternatives:
   - **Community Cloud's private app**: viewers invited by email sign in with Google or an emailed link, with no code
     change. But "You are only allowed one private app at a time", and every viewer must be invited.
   - **`st.login`** with Google or another OIDC provider, plus an e-mail allow-list in code: real identity. It needs an
     OIDC client, `[auth]` secrets and the Authlib package (a new dependency and a regenerated `uv.lock`).
3. **Python 3.13**, chosen in the deploy dialog's advanced settings. `pyproject.toml` and `uv.lock` require a version
   below 3.14, and Community Cloud defaults to the newest Python it supports.
4. **Dependencies**: nothing to add.
   - Community Cloud uses the first dependency file it finds, in the order `uv.lock`, `Pipfile`, `environment.yml`,
     `requirements.txt`, `pyproject.toml`. It will therefore install from `uv.lock`.
   - `uv.lock`'s pins match `pyproject.toml` (Streamlit 1.65.0, chromadb 1.5.9, onnxruntime 1.31.0, rapidocr 3.10.0),
     and it includes Linux wheels.
   - No `packages.txt` is needed: gpg is only used to build TARIC, and OCR uses `opencv-python-headless`.
5. **Secrets**: `OPENROUTER_API_KEY` and `CARGOLINT_APP_PASSWORD`. Optionally `CARGOLINT_WORKERS = "3"` and
   `ANONYMIZED_TELEMETRY = "False"`, which turns off Chroma's usage pings.

### 4.2 A demo store without any API call

All 192 demo rulings are in the local full index with identical embedded text. The nomenclature index and the BM25
file are the same in the demo and the full build. So a demo store can be cut from `store/` without any embedding call,
with a script of about 40 lines:

1. Copy `store/chroma/` and `store/bm25.pkl`.
2. Write `bti_docs.jsonl` for the chosen rulings.
3. Create a new `bti` collection from those rulings' vectors, read out of the full one with
   `get(ids=…, include=["embeddings", "documents", "metadatas"])`.
4. Write `index_meta.json` with the right counts.

`python -m rag.loader --demo` does not do this. On top of the existing full store it keeps all 1.8 GB of the ruling
index, because the index already holds at least as many vectors as the demo needs and the loader skips it.

**How many rulings.** `data/bti_demo.jsonl` holds 16 rulings per chapter, drawn at random. With so few, the nearest
rulings to a line are often unrelated goods. Either the vote fails and the line goes to review, or no ruling reaches the
0.40 similarity floor and the model's confidence decides. Either way the demo would not behave like the system the
README's evaluation figures describe. Two alternatives keep the votes meaningful, and the same script builds either one,
still without API calls:

- about 5,000 rulings, at about +95 MB of memory;
- the rulings under the sample's HS-6 codes and chapters.

### 4.3 Getting the store to the cloud

Sizes for the 192-ruling demo store plus TARIC: `store/chroma` 134 MB (its largest file 92.7 MB), `bm25.pkl` 4.9 MB,
`bti_docs.jsonl` 0.3 MB, `chroma-bti` about 5–10 MB, `index_meta.json` 1 KB, and `data/taric.jsonl` 29 MB. That is
about 175 MB raw and about 72 MB compressed (the vectors compress to about half, TARIC to 2 MB). Each further 1,000
rulings adds about 26 MB raw.

| Option | Changes | Size | Cold start | Trade-offs |
|---|---|---|---|---|
| **A. Commit the demo store** | `.gitignore`: `store/` becomes `store/*` plus `!store/demo/`, and `data/taric.jsonl` is no longer ignored; `STORE_DIR` overridable by `CARGOLINT_STORE_DIR` (1–2 lines in `agent/config.py`), set to `store/demo` in the secrets | about 175 MB in the working tree, about 72 MB of git history per version | instant | Simplest at run time. The 92.7 MB vector file is under GitHub's 100 MB file limit but over its 50 MB warning. The ruling index's vector file reaches 100 MB at about 6,000 rulings. Every rebuild adds about 70 MB to the public repository's history for good, and every clone and CI run downloads it. |
| **B. As A, with Git LFS** | as A, plus LFS rules in `.gitattributes` | git history stays small; LFS holds about 175 MB per version | instant after the clone | Community Cloud supports LFS: "If your GitHub repository uses LFS, it will just work". Every cold start, and every CI run that fetches LFS, draws about 175 MB from your GitHub LFS allowance (check its current size). A clone without LFS gets pointer files and the app crashes at `bm25.pkl`. |
| **C. Download at first start** (recommended) | About 25 lines in `load_kb()`. If `store/index_meta.json` is missing and `CARGOLINT_DEMO_STORE_URL` is set, it downloads the archive, checks its SHA-256 (also a setting) and unzips it into the repository root. The archive (`store/…` plus `data/taric.jsonl`) is a GitHub release asset. | nothing in git; an archive of about 72 MB | 10–30 s more on every cold start, after sleep or a reboot | The repository and CI are untouched, and local development is unaffected: the store exists, so nothing is downloaded. Release downloads use no LFS allowance, and any ruling count works. Costs: one more moving part (a URL and a checksum in the secrets) and a new asset per index rebuild. |
| **D. Build at first start** | run the loader's demo build inside `load_kb()` | nothing in git except TARIC | several minutes and about $0.02 of embeddings on every cold start | TARIC cannot be built there (it needs the signed raw files and gpg), so it still needs A or C. It also adds a memory peak during the build and pays again at every wake-up. Not recommended. |

**Recommendation**: C, because the repository is public. It keeps large files out of git history, allows any number of
rulings and uses no quota. A is the alternative with no moving parts, as long as the ruling index stays below about
6,000 rulings.

**Publishing the data.** A, B and C all publish the store and the TARIC snapshot. CN 2026 and EBTI are CC BY 4.0, with
the attribution already in the README. The TARIC snapshot comes from the Swedish Customs file distribution, which
publishes no formal licence. Confirm redistribution before publishing it, or keep the archive private: C with a private
download URL and a token in the secrets.

### 4.4 Change list for option C

1. A new script that cuts the demo store from the local full build, for example `python -m rag.demo_store`. No API
   call.
2. The download step in `load_kb()`: download, checksum, unzip (about 25 lines).
3. `agent/config.py`: `CARGOLINT_APP_PASSWORD`, `CARGOLINT_DEMO_STORE_URL` and `CARGOLINT_DEMO_STORE_SHA256`.
4. `app.py`: the password gate (about 15 lines) and, optionally, the missing-key message.
5. Community Cloud: Python 3.13, the secrets, and a dedicated OpenRouter key with a credit limit.
6. Offline tests for the gate and the download step (with a local archive), as Principle VII asks. New work goes
   through Spec Kit.

## 5. What the app writes to disk at run time

The app's own code writes nothing to disk while it runs:

- **Exports**: CSV, JSON and the audit trail are `st.download_button`s fed from bytes built in memory
  (`ui/main_page.py:149`, `ui/admin.py:96`).
- **Uploads**: parsed from memory (`io.BytesIO` in `tools/parsers.py` and `tools/ocr.py`); Streamlit keeps uploaded files
  in memory.
- **Shipments**: lines, decisions and the audit trail live in `st.session_state` (`app.py:get_store`), and the agent
  chat in `st.session_state["chat"]`.
- **Logs and caches**: logging goes to stderr only (`agent/config.py:configure_logging`); query embeddings and query
  expansions are cached in memory.

Writes that do happen:

- **Chroma** writes to its folders when the app opens them (SQLite journal files; `store/chroma-bti` here was modified
  today by being opened). On the cloud this is harmless, because the store is restored at every cold start.
- **A missing `store/chroma/`**, while `index_meta.json` exists, makes Chroma create an empty database there (§1).
- **RapidOCR** would download its models into `site-packages` only if they were missing. They ship in the wheel.
- **The command-line tools** are the only other writers: `python -m rag.loader` (`store/`, `data/`, `data/SOURCES.md`,
  `store/logs/`), `python -m rag.bti` and the price refresh in `agent/llm.py:refresh_prices`. None of them runs inside
  the app.

Because nothing the app relies on is written at run time, a reboot loses only the sessions themselves. In-progress
shipments and their audit trails exist only in memory. They are lost when the browser session ends, when the app
reboots, and when it sleeps: "All apps without traffic for 12 hours go to sleep". A clerk must export before leaving,
as when running locally; the difference is that on the cloud the reboots are outside your control.

## 6. Platform facts used, and sources

- **Resources**, as of February 2024 and changeable without notice: CPU 0.078–2 cores, memory 690 MB–2.7 GB, storage
  up to 50 GB. An app over its limits slows down or shows "This app has gone over its resource limits"
  ([Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app)).
- **Sleep**: apps without traffic for 12 hours sleep, and anyone who can view an app can wake it (same page).
- **Platform**: Debian 11 (bullseye), forward-slash paths; the working directory is the repository root.
  Community Cloud's overrides include `showErrorDetails = false` and `enableXsrfProtection = true`
  ([Status and limitations](https://docs.streamlit.io/deploy/streamlit-community-cloud/status),
  [File organization](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)).
- **Dependencies**: the first file found wins, in the order `uv.lock`, `Pipfile`, `environment.yml`, `requirements.txt`,
  `pyproject.toml`; apt packages go in `packages.txt`
  ([App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)).
  Only Python versions that still receive security updates are allowed (Status and limitations).
- **Git LFS**: "If your GitHub repository uses LFS, it will just work with Streamlit Community Cloud" (File
  organization).
- **Private apps**: viewers are invited by email; "You are only allowed one private app at a time"
  ([Share your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)).
- **Secrets**: entered in the app's settings
  ([Cloud secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)).
  Root-level secrets are also environment variables
  ([Secrets management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)); confirmed in the
  installed Streamlit 1.65 source (`web/bootstrap.py`, `runtime/secrets.py`).
- **Sign-in**: the reference shipped with Streamlit 1.65 (`.agents/skills/developing-with-streamlit/references/authentication.md`)
  recommends `st.login` over a password gate.
- **OpenRouter key limits**: a per-key credit limit with an optional daily, weekly or monthly reset
  ([Limits](https://openrouter.ai/docs/api_reference/limits),
  [Capping shared keys](https://openrouter.ai/docs/guides/best-practices/capping-shared-agent-keys)).

## Not verified

- **Linux memory**: memory was measured on Windows only, and the server and session overhead was not measured.
- **The filesystem after sleep**: the documentation doesn't say whether it survives. This assessment assumes it
  doesn't.
- **The demo's routing with a reduced ruling index**: measuring it would need paid evaluation runs.
- **Quotas and terms**: your current GitHub LFS allowance, and Swedish Customs' terms for redistributing the TARIC data.
