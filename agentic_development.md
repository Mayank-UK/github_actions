# AI defined section:

## Current state
- Plan APPROVED 2026-10-10. Video-coverage checklist below governs guide scope.
- P0 DONE (8a1baab): app/{facts,counter,image,frontend} + tests 9/7/5 green + non-root multi-arch Dockerfiles (builder `cilab-multi`). CI test cmds (P2 must reuse): pytest via venv or setup-python; `node --test "app/counter/*.test.js"` GLOB form (bare dir arg HANGS Node 22); go test needs setup-go or golang container (no host Go).
- P1 DONE (f035ab1): kind `cilab` cluster, kustomize base + overlays dev/staging/prod (ns cilab-*, hosts *.cilab.local, prod replicas 2), Taskfile ×9. E2E green: 16/16 pods, 3×200 + /api/facts + /api/count. Gotchas: ingress-nginx controller MUST node-select ingress-ready=true (task patches it); smoke retries 30s (nginx-sync 503s).
- P2 AUTHORING DONE (6b2050a): `.github/workflows/ci.yaml` — DAG test-matrix (facts pytest / counter npm ci + node --test glob / image setup-go cache:false no go.sum) → render ×3 (setup-kubectl + kubectl v1.36.1) → build-push ×4 (QEMU+buildx, `ghcr.io/<owner-lowercase>/cilab-*` tags `sha-<7>`+`dev`, cache type=gha); 11/11 `uses:` SHA-pinned; actionlint clean; union paths filter (no per-job gating). CI test deps installed inline (httpx, pytest) — follow-up: requirements-dev.txt. LIVE RUN PENDING on user repo creation + push. Repo NAME (user decision 2026-10-10): `Mayank-UK/github_actions` (private) — no code references the repo name (owner derived dynamically; images keep the `cilab-*` app prefix).
- RENAME DONE (a939404 + a69e4a6 fixup): `cilab` → `github-actions` EVERYWHERE (images `github-actions-<svc>` on GHCR, cluster `github-actions`, ns `github-actions-{dev,staging,prod}`, hosts `*.github-actions.local`, builder `github-actions-multi`; grep 0 hits). ci.yaml gained `workflow_dispatch` + `skip-build` input gating build-push. Cluster recreated, smoke ×3 + /api/facts green. Taskfile fix: deploy-all `load` now runs after `build` (deps race). User pushed initial history (c09d1e7, incl. agentic_development.md); 0 Actions runs = known paths-filter-on-first-push quirk, next matching push triggers. Awaiting user push of rename commits → first live CI run.
- HOSTS FIX (ae5e926): `*.github-actions.local` → `*.github-actions.test` — macOS reserves `.local` for Bonjour/mDNS so browsers hang forever on it (user-verified; classic gotcha, teach it in the guide's devex section). Overlays + base placeholder + Taskfile smoke/hosts renamed; apply ×3 + smoke green. User still must run `task hosts` once for browser access. First live CI run triggered by user's push (run #1, push event) — green status unconfirmed; P2 closes on confirmed green.
- Scout facts: k8slab (`../kubernetes`) = 5 services on a kind 3-node cluster (local-only, currently deleted), flat numbered manifests, local-only images, no registry, no tests. Course fork teaches secrets/environments/OIDC/reusable workflows but has NO docker-push or k8s-deploy example — we write those from scratch.

## CI/CD plan (approved 2026-10-10)
Decisions:
- App "cilab": trimmed k8slab clone — 4 services (facts Python :8000, counter Node :3000, image Go :8080, frontend nginx :80 proxying /api) + real tests (pytest / node --test / go test). loadgen dropped (was HPA demo only).
- Layout: `app/<svc>/` source, `.docker/` multi-stage non-root Dockerfiles, `.k8s/base` + `.k8s/overlays/{dev,staging,prod}` (kustomize — standard replacement for k8slab's flat manifests), `.github/workflows/`.
- This dir becomes its OWN git repo (git init; parent devops repo leaves it untracked) — workflows must sit at a real GitHub repo root.
- Registry: GHCR (`ghcr.io/<user>/cilab-*`) via built-in GITHUB_TOKEN (`packages: write`) — zero stored credentials.
- CI on GitHub-hosted runners: PRs + development push → per-language lint/test matrix → docker buildx multi-arch (amd64+arm64, QEMU — arm64 is REQUIRED: kind nodes on the M-series Mac are arm64) push, tag `sha-<short>`.
- CD on self-hosted runner (docker container on the Mac, label `deploy-local`, outbound-only connection): kustomize set image → `kubectl apply -k` overlay → `kubectl rollout status` gate. One kind cluster, namespaces dev/staging/prod, one ingress host per env.
- GitHub environments: dev = auto on push to development; staging = auto on merge to staging; production = protected (required reviewer = manual approval) on merge to production. Concurrency group per env.
- "Expose local to internet" → NOT needed: self-hosted runner dials OUT to GitHub, no inbound ports. Tunneling the kube API (ngrok/cloudflare) rejected as non-standard + unsafe.
- Secrets stay GitHub-encrypted; no kubeconfig secret needed (runner is local). SOPS/sealed-secrets = optional later extension.
- Teaching guide = markdown SSoT (`docs/guide/*.md`) SERVED BY the frontend service: nginx homepage IS the guide (vendored client-side markdown renderer — sidebar, search, code highlighting, offline, no CDN, no React toolchain), `/api/*` still proxied to backends so guide pages get inline live demos against the running services. Run the project → it teaches (user's guide-family property); same files read fine on GitHub. express_developers_guide anatomy: concept → text → GitHub-UI where-to-click (Actions tab, Settings→Secrets, Environments, protection rules) → snippet SOURCED from our repo (invariant "code is the source of truth": every snippet captioned `source: <path>`; a check script in CI verifies snippets exist in those files — the pipeline validates its own guide). Part I fundamentals A–Z (events, jobs/steps/runners incl. self-hosted, GITHUB_TOKEN + permissions, secrets vs variables, environments + protection, cache, artifacts, matrix, concurrency, reusable workflows, OIDC overview, act/debugging). Part II = "Project": our app + pipeline end-to-end, every workflow quoted. Guide content written AFTER workflows exist (code first, then quote).
- Video-coverage checklist — guide Part I must include EVERY course-video topic ([x] real snippet/impl from our repo · [c] concept-only prose):
    - Core: history & why-GHA (tool timeline; vs GitLab/CircleCI/Jenkins) [c] · event/workflow/job/step/runner + DAG `needs` [x] · env scoping + GITHUB_ENV/GITHUB_OUTPUT + job outputs via needs [x] · contexts (github/env/matrix/secrets/vars/steps/needs) [x] · event filters (branch/path/dispatch-inputs/cron) [x/c] · `if:` conditionals [x]
    - Actions: marketplace vetting + pin `uses:` to 40-char commit SHA [x — every action in our workflows pinned] · authoring: composite action [x — we ship one], reusable workflow [x], JS/container actions [c]
    - Security: secrets vs vars + environment protection [x] · GITHUB_TOKEN least-privilege [x] · OIDC [c] · self-hosted fork-PR hardening [x]
    - Build: artifacts vs actions/cache vs buildx gha cache [x] · matrix + fail-fast [x] · concurrency [x] · workflow commands (::group/::error) [x] · jobs.container [c]
    - Patterns: language-runtime test [x] · multi-arch build+push [x] · changed-files/paths-filter [c] · GitOps vs push-deploy [c] · release-please/semver [c] · stale-bot + OTel timing export [c — named only, out of scope]
    - DevEx/best-practices: Taskfile local-first loop [x] · act [c] · SSH breakpoint + debug vars [c] · monorepo vs multi-repo [c]

Phases:
- P0 ✅ scaffold: git init + .gitignore, app code + tests + Dockerfiles — verified: 3 test suites + `docker build` ×4 + multi-arch ×4 green
- P1 ✅ k8s: kind config + kustomize base/overlays + Taskfile — verified: 3 envs live on local kind, smoke ×3 green
- P2 🚧 CI workflows (all `uses:` pinned to commit SHAs) — needs user to create private GitHub repo + push — verify: green Actions run
- P3 ⏳ CD: runner container (fork-PR hardened) + deploy workflows + one composite action — needs user to register the runner — verify: e2e dev deploy from a push
- P4 ⏳ environments + production protection rule — needs user clicks in GitHub UI — verify: dev→staging→prod promotion e2e with approval gate
- P5 ⏳ manual-setup guide (README) + devlog
- P6 ⏳ guide: Part I fundamentals A–Z + Part II Project in `docs/guide/*.md`, frontend serves it at `/` (renderer vendored into image); snippet-check script wired into CI — verify: check passes in Actions + guide renders at localhost:8080 with live demos

# Developer defined section:

- Project requirements
    - I want to practice CICD pipeline workflow using github actions, please build a flow the most industry standard way, I usually keep branches development, staging, and production. Do whatever is the best practice like storing credentials encrypted way, uses, etc, whatever is the industry standard, later just tell me what needs to be done from my side. I had also downloaded a fork of a tutor teaching github actions "devops-directive-github-actions-course" present alongside this projects folder
    - Include GitHub Actions fundamentals taught A–Z in a written guide (express_developers_guide teaching style: concept → GitHub-UI where-to-click → code snippet), covering secrets, cache, artifacts, environments, matrix, etc. — every snippet quoted from OUR project files, and the project itself in its own separate "Project" section of the guide ⏳
    - We will have similar app like we have as a sample for devops/kubernetes .The whole app will be containerized and orchestrated using kubernetes like my other apps express_developers_guide, devops/kubernetes, etc, right now I am not sure where will I deploy, but my goal was to expose my local setup to outside internet which is then used by github actions to deploy, not sure if this is possible
    - You will write yaml files for all this setup

- Generic instructions:
    - Follow the most standard approach in industry, I don't want custom hack and slash solutions
    - Update the status markers: ✅ done · 🚧 in progress · ⏳ pending for the tasks

- Development tasks:
    - First write the plan here what you are going to do, then I will approve ✅ (approved 2026-10-10)
    - After you are done, you can guide me what I need to setup my manually like github secrets, cloud account creation and configs, etc ⏳
