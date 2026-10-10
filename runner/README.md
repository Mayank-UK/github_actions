# Self-hosted deploy runner (this Mac, native process)

The deploy jobs (`deploy-dev`, `deploy-staging`, `deploy-production`) run on a
self-hosted runner with the label `deploy-local` living natively on this Mac,
next to the kind cluster it deploys to.

## Why a NATIVE process and not a container

kind's API server port is published on the Mac's loopback
(`https://127.0.0.1:<port>` — Docker Desktop maps it to the kind container).
A runner running inside a Docker container cannot reach the Mac's `localhost`:
Docker Desktop on macOS has no real host networking, so `127.0.0.1` inside a
container is the container itself, not the host. A native runner process
shares the host's network stack and reaches the kind API server directly.

No inbound access is needed either way: the runner long-polls GitHub over
outbound HTTPS. Nothing listens publicly on this Mac because of the runner.

## One-time setup

### 1. Tools (pinned versions)

```sh
brew install kubectl kustomize
kubectl version --client   # expect 1.36.x — matches CI's setup-kubectl v1.36.1
kustomize version          # expect 5.8.x — standalone binary; `kustomize edit`
                           # is NOT part of kubectl
```

If brew ever ships a kubectl newer than 1.36.x, pin the exact binary instead:

```sh
curl -LO "https://dl.k8s.io/release/v1.36.1/bin/darwin/arm64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/kubectl
```

`git` is already present (Xcode Command Line Tools).

The kind cluster itself is managed from the repo root as usual:
`task cluster-create && task ingress`.

### 2. Register the runner

GitHub → `Mayank-UK/github_actions` → **Settings → Actions → Runners →
New self-hosted runner → macOS**. Download the **Apple silicon (arm64)**
tarball (this is an M-series Mac) into a directory OUTSIDE any repo checkout
(e.g. `~/runners/github-actions/`), then:

```sh
./config.sh --url https://github.com/Mayank-UK/github_actions \
            --token <registration-token-from-the-page> \
            --labels deploy-local \
            --name mac-local
```

`--labels deploy-local` is what the deploy jobs select with
`runs-on: [self-hosted, deploy-local]`.

### 3. Run it

```sh
./run.sh                              # foreground, in a spare terminal
# or headless:
nohup ./run.sh > runner.log 2>&1 &
# or as a managed service (starts at login):
# ./svc.sh install && ./svc.sh start
```

While the runner is offline, deploy jobs simply queue on GitHub and run when
it comes back.

### 4. The GHCR pull token (repo secret)

The deploy workflows create an `imagePullSecret` named `ghcr-pull` in each
namespace from the repository secret **`GHCR_PULL_TOKEN`** — a classic PAT
with the `read:packages` scope (create at <https://github.com/settings/tokens>).
Add it once: **Settings → Secrets and variables → Actions → New repository
secret**. Locally, `task pull-secret` applies the same secret using the env
var of the same name.

## Security — private repo, your Mac

- This repository is **private** and must STAY private while the runner is
  attached: making it public would let anyone open a PR whose workflow code
  runs on this Mac.
- Keep fork-PR workflow execution disabled: **Settings → Actions → General →
  Fork pull request workflows** — leave "Require approval for all external
  contributors" (the safe default) or stricter; never allow fork pull
  requests to run workflows without approval.
