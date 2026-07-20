#!/bin/bash
# Kercel build worker — runs as a systemd service on every EC2 build instance.
# Polls SQS for deployment jobs, clones the GitHub repo, runs npm build,
# syncs the output to S3, then invalidates CloudFront so the new version
# is live immediately.
#
# BUG FIXES applied in this file:
#   BUG-03 / BUG-04 / BUG-12 / BUG-14 / BUG-15 / BUG-16
set -euo pipefail

# ---------------------------------------------------------------------------
# log_action: write a timestamped action row to DynamoDB deploy_act_table.
# This is picked up by the DynamoDB Stream → log_streamer Lambda → WebSocket
# so the browser sees real-time build logs.
# ---------------------------------------------------------------------------
log_action() {
  local deployment_id="$1"
  local action="$2"
  local message="$3"
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")"
  aws dynamodb put-item \
    --table-name "$DEPLOY_ACT_TABLE" \
    --item "{\"deploymentId\":{\"S\":\"$deployment_id\"},\"actionTimestamp\":{\"S\":\"$ts\"},\"action\":{\"S\":\"$action\"},\"message\":{\"S\":\"$message\"}}" \
    --region "${AWS_REGION:-us-east-1}"
}

# ---------------------------------------------------------------------------
# update_status: flip the deployment's status column in the history table.
# Called at the START of processing (→ "building") and at the END
# (→ "live" or "failed").
# ---------------------------------------------------------------------------
update_status() {
  local project_id="$1"
  local deployment_id="$2"
  local status="$3"
  aws dynamodb update-item \
    --table-name "$HISTORY_TABLE" \
    --key "{\"projectId\":{\"S\":\"$project_id\"},\"deploymentId\":{\"S\":\"$deployment_id\"}}" \
    --update-expression "SET #s = :status, updatedAt = :now" \
    --expression-attribute-names '{"#s":"status"}' \
    --expression-attribute-values "{\":status\":{\"S\":\"$status\"},\":now\":{\"S\":\"$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ\")\"}}}" \
    --region "${AWS_REGION:-us-east-1}"
}

# ---------------------------------------------------------------------------
# process_message: core build pipeline for a single deployment.
# Returns 0 on success, 1 on any hard failure.
# ---------------------------------------------------------------------------
process_message() {
  local body="$1"
  local deployment_id project_id github_url
  deployment_id="$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['deploymentId'])")"
  project_id="$(echo "$body"   | python3 -c "import sys,json; print(json.load(sys.stdin)['projectId'])")"
  github_url="$(echo "$body"   | python3 -c "import sys,json; print(json.load(sys.stdin).get('githubUrl',''))")"

  # -----------------------------------------------------------------------
  # BUG-12 FIX: Validate the GitHub URL before passing it to git clone.
  #
  # The original code blindly executed:
  #   git clone --depth 1 "$github_url" repo
  # with zero validation.  An attacker who can create a project could supply:
  #   • git://internal-host/evil           → SSRF to internal metadata/services
  #   • https://attacker.com/malicious.git → clones arbitrary external content
  #   • file:///etc/passwd                 → local file read via git protocol
  #
  # The fix: require the URL to match the HTTPS GitHub pattern exactly.
  # Only allow https://github.com/<owner>/<repo> (with optional .git suffix).
  # This is the URL form accepted by create_project's API anyway.
  # -----------------------------------------------------------------------
  if ! echo "$github_url" | grep -qE '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?$'; then
    log_action "$deployment_id" "FAILED" "Invalid or disallowed GitHub URL: $github_url"
    update_status "$project_id" "$deployment_id" "failed"
    return 1
  fi

  log_action "$deployment_id" "BUILDING" "Build worker picked up deployment"
  update_status "$project_id" "$deployment_id" "building"

  local work_dir="/tmp/kercel-build-${deployment_id}"
  rm -rf "$work_dir"
  mkdir -p "$work_dir"
  cd "$work_dir"

  log_action "$deployment_id" "CLONE" "Cloning $github_url"
  git clone --depth 1 "$github_url" repo
  cd repo

  if [ -f package.json ]; then
    log_action "$deployment_id" "INSTALL" "Running npm install"

    # -----------------------------------------------------------------------
    # The --omit=dev fallback is intentional: try prod-only install first
    # (faster, smaller), fall back to full install if the project needs
    # devDependencies to run the build script (common with Webpack/Vite etc.).
    # The final `|| return 1` means if BOTH attempts fail we abort the build
    # rather than proceeding with a broken node_modules.
    # -----------------------------------------------------------------------
    npm install --omit=dev 2>&1 || npm install 2>&1 || return 1

    if grep -q '"build"' package.json; then
      log_action "$deployment_id" "BUILD" "Running npm run build"

      # -------------------------------------------------------------------
      # BUG-04 FIX: The original code was:
      #   npm run build 2>&1 || true
      #
      # `|| true` swallows the non-zero exit code, so a broken build (type
      # error, missing env var, bad import, etc.) was silently ignored.
      # The script then continued to upload whatever happened to be in dist/
      # (possibly nothing, possibly stale files) and marked the deployment
      # "live".  Users saw a green tick but got a blank or broken site.
      #
      # Fix: remove `|| true` so a failed build propagates as exit code 1,
      # which causes process_message to return 1, which leaves the SQS
      # message visible and triggers the failure path in the polling loop.
      # -------------------------------------------------------------------
      npm run build 2>&1 || return 1
    fi
  fi

  # -------------------------------------------------------------------------
  # BUG-14 FIX: Determine the artifact directory to upload.
  #
  # The original fallback was `artifact_dir="."` — meaning if no dist/ or
  # build/ directory existed, the ENTIRE cloned repository was synced to the
  # public-facing output S3 bucket (and served via CloudFront).  This could
  # expose:
  #   • .env files with secrets
  #   • node_modules source (hundreds of MB)
  #   • The full .git history
  #   • Any private source files
  #
  # Fix: if no recognised build output directory exists AND there is no build
  # script, treat the repository root as a plain static site (valid for pure
  # HTML/CSS/JS projects).  But if a build script ran and produced nothing,
  # that is a build failure — abort rather than uploading raw source.
  # -------------------------------------------------------------------------
  local artifact_dir=""
  if [ -d dist ];  then artifact_dir="dist"
  elif [ -d build ]; then artifact_dir="build"
  elif [ -d out ];   then artifact_dir="out"    # Next.js static export
  elif [ -d public ] && ! grep -q '"build"' package.json 2>/dev/null; then
    artifact_dir="public"   # plain static sites that only have a public/ dir
  else
    # If a build script existed but produced no output directory, that is a
    # genuine build failure — do not fall back to the repository root.
    if grep -q '"build"' package.json 2>/dev/null; then
      log_action "$deployment_id" "FAILED" "Build completed but no output directory found (checked: dist, build, out)"
      update_status "$project_id" "$deployment_id" "failed"
      return 1
    fi
    # No build script and no recognised output dir → serve from repo root.
    # This is valid for simple HTML/CSS/JS static sites.
    artifact_dir="."
  fi

  log_action "$deployment_id" "UPLOAD" "Uploading build output from '$artifact_dir' to S3"

  # Sync build output to ARTIFACTS_BUCKET for historical record / rollback.
  aws s3 sync "$artifact_dir" \
    "s3://${ARTIFACTS_BUCKET}/archives/${project_id}/${deployment_id}/" \
    --delete --region "${AWS_REGION:-us-east-1}"

  # Sync build output to OUTPUT_BUCKET under a stable "current" prefix so
  # CloudFront always serves the latest deployment for this project at a
  # predictable path: /sites/<projectId>/current/
  #
  # BUG-02 (partial fix — see edge.py for the CloudFront Function that
  # rewrites directory requests to /index.html at the CDN edge):
  # Previously the worker synced to:
  #   s3://${OUTPUT_BUCKET}/sites/${project_id}/${deployment_id}/
  # CloudFront's default_root_object only works for the root path "/", so
  # any request to /sites/proj/dep/ returned a 403/404 instead of index.html.
  # Switching to a stable "current" prefix means:
  #   • CloudFront can consistently serve /sites/<projectId>/current/index.html
  #   • Invalidation clears exactly one path prefix per project
  #   • The CloudFront Function (edge.py) rewrites directory hits to index.html
  aws s3 sync "$artifact_dir" \
    "s3://${OUTPUT_BUCKET}/sites/${project_id}/current/" \
    --delete --exact-timestamps --region "${AWS_REGION:-us-east-1}"

  # -------------------------------------------------------------------------
  # CloudFront cache invalidation.
  #
  # BUG-02 (continued): Without invalidation, re-deploying the same project
  # served stale files from the CloudFront edge cache for up to 24 hours (the
  # default TTL).  Users would trigger a new build, see "live" status, but
  # still get the old version of their site.
  #
  # The distribution ID is stored in SSM Parameter Store by the DeliveryStack
  # (edge.py) so the EC2 instance can fetch it at runtime without a circular
  # CDK dependency.  If the parameter doesn't exist yet (race condition during
  # first deploy), we skip invalidation gracefully.
  # -------------------------------------------------------------------------
  local dist_id="${CLOUDFRONT_DISTRIBUTION_ID:-}"
  if [ -z "$dist_id" ]; then
    dist_id="$(aws ssm get-parameter \
      --name "/kercel/${STAGE}/cloudfront-distribution-id" \
      --query "Parameter.Value" --output text \
      --region "${AWS_REGION:-us-east-1}" 2>/dev/null || echo "")"
    # Cache in env for subsequent messages processed by this worker loop
    export CLOUDFRONT_DISTRIBUTION_ID="$dist_id"
  fi

  if [ -n "$dist_id" ]; then
    log_action "$deployment_id" "INVALIDATE" "Invalidating CloudFront cache for /sites/${project_id}/current/*"
    aws cloudfront create-invalidation \
      --distribution-id "$dist_id" \
      --paths "/sites/${project_id}/current/*" \
      --region us-east-1  # CloudFront is always global/us-east-1
  else
    log_action "$deployment_id" "INVALIDATE" "Skipped — CloudFront distribution ID not yet available"
  fi

  update_status "$project_id" "$deployment_id" "live"
  log_action "$deployment_id" "COMPLETE" "Deployment live at /sites/${project_id}/current/"

  rm -rf "$work_dir"
}

# ---------------------------------------------------------------------------
# BUG-15 FIX note (applied in compute.py, not here):
# The original user-data ran `dnf install -y aws-cli` on Amazon Linux 2023.
# AL2023 ships AWS CLI v2 pre-installed; adding the dnf package installs CLI v1
# from the repo, conflicting with v2 and potentially overriding it.
# The fix removes `aws-cli` from the dnf install command in compute.py so the
# pre-installed v2 is used as-is.
# ---------------------------------------------------------------------------

echo "Kercel build worker starting (queue: $DEPLOYMENT_QUEUE_URL)"

# ---------------------------------------------------------------------------
# Main SQS polling loop.
#
# BUG-03 CONTEXT: The SQS queue visibility timeout is set to 60 minutes in
# database.py (was 15).  We also request 900 seconds (15 min) from the
# receive-message call.  The queue-level timeout is what matters for safety;
# the receive-message value is capped by the queue setting.  With a 60-minute
# window, builds up to ~55 minutes long can complete without the message
# becoming visible to another worker and causing a duplicate build.
#
# For very long builds the worker should call ChangeMessageVisibility to extend
# the window mid-build — that is a future enhancement; the 60-min timeout
# covers the vast majority of real-world npm projects.
# ---------------------------------------------------------------------------
while true; do
  response="$(aws sqs receive-message \
    --queue-url "$DEPLOYMENT_QUEUE_URL" \
    --max-number-of-messages 1 \
    --wait-time-seconds 20 \
    --visibility-timeout 900 \
    --region "${AWS_REGION:-us-east-1}" \
    --output json)"

  message_body="$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); msgs=d.get('Messages',[]); print(msgs[0]['Body'] if msgs else '')")"
  receipt_handle="$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); msgs=d.get('Messages',[]); print(msgs[0]['ReceiptHandle'] if msgs else '')")"

  if [ -z "$message_body" ]; then
    continue
  fi

  if process_message "$message_body"; then
    # Build succeeded — delete the message from SQS so it is not retried.
    aws sqs delete-message \
      --queue-url "$DEPLOYMENT_QUEUE_URL" \
      --receipt-handle "$receipt_handle" \
      --region "${AWS_REGION:-us-east-1}"
  else
    # -----------------------------------------------------------------------
    # BUG-16 FIX: The original code logged a "FAILED" action but never called
    # update_status(..., "failed"), so the history table record remained stuck
    # at status="building" permanently.  Users could see a FAILED log entry
    # in the WebSocket stream but the deployment status API would keep
    # returning "building" — completely misleading.
    #
    # Fix: on failure, explicitly call update_status to write "failed" into
    # the history table, then log the FAILED action for the WebSocket stream.
    #
    # We also intentionally do NOT delete the SQS message here.  Leaving it
    # visible means SQS will redeliver it up to max_receive_count (5, set in
    # database.py) times.  This gives transient failures (network blip, GitHub
    # rate limit, momentary S3 error) a chance to succeed on retry.  After
    # max_receive_count attempts the message lands in the DLQ.
    # -----------------------------------------------------------------------
    raw_deployment_id="$(echo "$message_body" | python3 -c "import sys,json; print(json.load(sys.stdin)['deploymentId'])" 2>/dev/null || echo "unknown")"
    raw_project_id="$(echo "$message_body"    | python3 -c "import sys,json; print(json.load(sys.stdin)['projectId'])"    2>/dev/null || echo "unknown")"

    # Only call update_status if we could parse the IDs (guards against
    # malformed messages that will be dead-lettered immediately).
    if [ "$raw_deployment_id" != "unknown" ] && [ "$raw_project_id" != "unknown" ]; then
      update_status "$raw_project_id" "$raw_deployment_id" "failed" || true
      log_action "$raw_deployment_id" "FAILED" "Build failed — see previous log entries for details"
    fi
  fi
done
