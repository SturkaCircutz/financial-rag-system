#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${AWS_CLI:-}" ]]; then
  if command -v aws >/dev/null 2>&1; then
    AWS_CLI="aws"
  elif [[ -x "$HOME/.local/bin/aws" ]]; then
    AWS_CLI="$HOME/.local/bin/aws"
  else
    AWS_CLI="aws"
  fi
fi

TABLE_NAME="${REPORTS_DYNAMODB_TABLE_NAME:-financial-rag}"
REGION="${AWS_REGION:-us-east-1}"
ENDPOINT_URL="${REPORTS_DYNAMODB_ENDPOINT_URL:-http://localhost:8000}"

if ! command -v "$AWS_CLI" >/dev/null 2>&1; then
  echo "aws CLI is required. Install it or set AWS_CLI to its full path."
  exit 127
fi

case "$ENDPOINT_URL" in
  http://localhost:*|http://127.0.0.1:*|http://[::1]:*) ;;
  *)
    echo "Refusing to create a remote DynamoDB table. Set REPORTS_DYNAMODB_ENDPOINT_URL to DynamoDB Local."
    exit 2
    ;;
esac

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-local}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-local}"
export AWS_EC2_METADATA_DISABLED="${AWS_EC2_METADATA_DISABLED:-true}"

aws_args=(--region "$REGION" --endpoint-url "$ENDPOINT_URL")

if "$AWS_CLI" dynamodb describe-table --table-name "$TABLE_NAME" "${aws_args[@]}" >/dev/null 2>&1; then
  echo "DynamoDB Local table already exists: $TABLE_NAME"
  exit 0
fi

"$AWS_CLI" dynamodb create-table \
  --table-name "$TABLE_NAME" \
  --billing-mode PAY_PER_REQUEST \
  --attribute-definitions \
    AttributeName=PK,AttributeType=S \
    AttributeName=SK,AttributeType=S \
    AttributeName=GSI1PK,AttributeType=S \
    AttributeName=GSI1SK,AttributeType=S \
  --key-schema \
    AttributeName=PK,KeyType=HASH \
    AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes \
    "IndexName=GSI1,KeySchema=[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}],Projection={ProjectionType=ALL}" \
  "${aws_args[@]}"

"$AWS_CLI" dynamodb wait table-exists --table-name "$TABLE_NAME" "${aws_args[@]}"
echo "DynamoDB Local table ready: $TABLE_NAME"
