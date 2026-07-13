#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/remote-run.sh '<command>' ['<artifact paths>'] ['<artifact budget>'] '<worker label>'

Examples:
  scripts/remote-run.sh 'uname -a && pwd' 'run-output/' '96K' 'worker-97-4'
  REMOTE_RUN_REF=main scripts/remote-run.sh 'date -u' 'run-output/' '96K' 'worker-97-4'
  REMOTE_RUN_WORKER=worker-97-4 scripts/remote-run.sh 'date -u'

Environment:
  REMOTE_RUN_REPO       GitHub repo, for example MmMmaru/vllm-ascend.
  REMOTE_RUN_REF        Git ref to run. Defaults to the current branch.
  REMOTE_RUN_WORKFLOW   Workflow file. Defaults to internal-command.yml.
  REMOTE_RUN_WORKER     Self-hosted runner label. Used when the fourth
                        positional argument is omitted.
EOF
}

github_repo_from_origin() {
  local url
  url="$(git remote get-url origin)"

  case "${url}" in
    https://github.com/*/*.git)
      url="${url#https://github.com/}"
      echo "${url%.git}"
      ;;
    https://github.com/*/*)
      echo "${url#https://github.com/}"
      ;;
    git@github.com:*/*.git)
      url="${url#git@github.com:}"
      echo "${url%.git}"
      ;;
    git@github.com:*/*)
      echo "${url#git@github.com:}"
      ;;
    *)
      echo "Cannot infer GitHub repo from origin: ${url}" >&2
      return 1
      ;;
  esac
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "$#" -lt 1 ]]; then
  usage
  exit 0
fi

command_to_run="$1"
artifact_paths="${2:-run-output/}"
artifact_budget="${3:-96K}"
worker="${4:-${REMOTE_RUN_WORKER:-}}"

if [[ -z "${worker}" ]]; then
  echo "A self-hosted runner label is required as the fourth argument or REMOTE_RUN_WORKER." >&2
  usage >&2
  exit 2
fi

repo="${REMOTE_RUN_REPO:-$(github_repo_from_origin)}"
ref="${REMOTE_RUN_REF:-$(git branch --show-current)}"
workflow="${REMOTE_RUN_WORKFLOW:-internal-command.yml}"
run_key="remote-$(date -u +%Y%m%dT%H%M%SZ)-${RANDOM}"
output_dir="output/${run_key}"

echo "repo=${repo}"
echo "ref=${ref}"
echo "workflow=${workflow}"
echo "worker=${worker}"
echo "run_key=${run_key}"

run_id="$(
  gh api \
    --method POST \
    --header "Accept: application/vnd.github+json" \
    --header "X-GitHub-Api-Version: 2026-03-10" \
    "repos/${repo}/actions/workflows/${workflow}/dispatches" \
    --raw-field "ref=${ref}" \
    --raw-field "inputs[run_key]=${run_key}" \
    --raw-field "inputs[worker]=${worker}" \
    --raw-field "inputs[command]=${command_to_run}" \
    --raw-field "inputs[artifact_paths]=${artifact_paths}" \
    --raw-field "inputs[artifact_budget]=${artifact_budget}" \
    --jq ".workflow_run_id"
)"

if [[ ! "${run_id}" =~ ^[0-9]+$ ]]; then
  echo "Workflow dispatch did not return a valid workflow_run_id: ${run_id}" >&2
  exit 1
fi

echo "run_id=${run_id}"
echo "url=https://github.com/${repo}/actions/runs/${run_id}"

set +e
gh run watch "${run_id}" \
  --repo "${repo}" \
  --interval 15 \
  --exit-status
watch_status="$?"
set -e
script_status="${watch_status}"

mkdir -p "${output_dir}"
echo "Downloading artifact to ${output_dir}"
if gh run download "${run_id}" \
  --repo "${repo}" \
  --name "internal-command-${run_key}" \
  --dir "${output_dir}"; then
  echo "Downloaded files:"
  find "${output_dir}" -type f | sort

  if [[ -f "${output_dir}/files/run-output/command.log" ]]; then
    echo
    echo "===== command.log ====="
    sed -n '1,240p' "${output_dir}/files/run-output/command.log"
  fi

  if [[ -f "${output_dir}/files/run-output/exit-code.txt" ]]; then
    remote_status="$(head -n 1 "${output_dir}/files/run-output/exit-code.txt")"
    if [[ "${remote_status}" =~ ^[0-9]+$ ]]; then
      script_status="${remote_status}"
    fi
  fi
else
  echo "Artifact download failed. Check the run logs:" >&2
  echo "https://github.com/${repo}/actions/runs/${run_id}" >&2
fi

conclusion="$(
  gh run view "${run_id}" \
    --repo "${repo}" \
    --json conclusion \
    --jq ".conclusion"
)"
echo "conclusion=${conclusion}"

exit "${script_status}"
