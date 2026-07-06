#!/bin/bash
set -euo pipefail

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

update_status() {
  local project_id="$1"
  local deployment_id="$2"
  local status="$3"
  aws dynamodb update-item \
    --table-name "$HISTORY_TABLE" \
    --key "{\"projectId\":{\"S\":\"$project_id\"},\"deploymentId\":{\"S\":\"$deployment_id\"}}" \
    --update-expression "SET #s = :status, updatedAt = :now" \
    --expression-attribute-names '{"#s":"status"}' \
    --expression-attribute-values "{\":status\":{\"S\":\"$status\"},\":now\":{\"S\":\"$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")\"}}" \
    --region "${AWS_REGION:-us-east-1}"
}

process_message() {
  local body="$1"
  local deployment_id project_id github_url
  deployment_id="$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['deploymentId'])")"
  project_id="$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin)['projectId'])")"
  github_url="$(echo "$body" | python3 -c "import sys,json; print(json.load(sys.stdin).get('githubUrl',''))")"

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
    npm install --omit=dev 2>&1 || npm install 2>&1 || true
    if grep -q '"build"' package.json; then
      log_action "$deployment_id" "BUILD" "Running npm run build"
      npm run build 2>&1 || true
    fi
  fi

  local artifact_dir="dist"
  if [ ! -d dist ] && [ -d build ]; then artifact_dir="build"; fi
  if [ ! -d "$artifact_dir" ] && [ ! -d dist ] && [ ! -d build ]; then artifact_dir="."; fi

  log_action "$deployment_id" "UPLOAD" "Uploading artifacts to S3"
  aws s3 sync "$artifact_dir" "s3://${ARTIFACTS_BUCKET}/artifacts/${project_id}/${deployment_id}/" --delete
  aws s3 sync "$artifact_dir" "s3://${OUTPUT_BUCKET}/sites/${project_id}/${deployment_id}/" --delete

  update_status "$project_id" "$deployment_id" "live"
  log_action "$deployment_id" "COMPLETE" "Deployment live"

  rm -rf "$work_dir"
}

echo "Kercel build worker starting (queue: $DEPLOYMENT_QUEUE_URL)"

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
    aws sqs delete-message \
      --queue-url "$DEPLOYMENT_QUEUE_URL" \
      --receipt-handle "$receipt_handle" \
      --region "${AWS_REGION:-us-east-1}"
  else
    log_action "$(echo "$message_body" | python3 -c "import sys,json; print(json.load(sys.stdin)['deploymentId'])")" "FAILED" "Build failed"
  fi
done
