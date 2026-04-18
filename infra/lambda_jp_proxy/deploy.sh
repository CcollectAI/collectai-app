#!/usr/bin/env bash
# Deploy the JP-region HTML proxy to AWS Lambda in ap-northeast-1 (Tokyo).
#
# Prerequisites (one-time):
#   1. AWS CLI installed + configured with a profile that has:
#        - AWSLambda_FullAccess
#        - IAMFullAccess (for first-time role creation)
#      Either run `aws configure --profile collectai-lambda` or set
#      AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in your environment.
#   2. openssl available for generating the shared secret.
#
# What it does:
#   - Creates execution role (idempotent)
#   - Zips and deploys the Lambda function
#   - Creates a Function URL with CORS disabled and no auth (we use a
#     header-based shared secret)
#   - Prints the URL + secret for you to add to EC2 .env
#
# Usage:
#   ./deploy.sh                   # first deploy
#   ./deploy.sh update-code       # redeploy without re-creating resources

set -euo pipefail

REGION="ap-northeast-1"
FN_NAME="collectai-jp-proxy"
ROLE_NAME="collectai-jp-proxy-role"
ZIP_PATH="/tmp/${FN_NAME}.zip"
PROFILE="${AWS_PROFILE:-default}"

cd "$(dirname "$0")"

step() { printf "\n\033[1;34m▶ %s\033[0m\n" "$*"; }

step "Packaging handler.py into $ZIP_PATH"
rm -f "$ZIP_PATH"
zip -j "$ZIP_PATH" handler.py

if [[ "${1:-}" == "update-code" ]]; then
  step "Updating function code only"
  aws lambda update-function-code \
    --region "$REGION" \
    --function-name "$FN_NAME" \
    --zip-file "fileb://$ZIP_PATH" \
    --profile "$PROFILE" >/dev/null
  echo "Code updated."
  exit 0
fi

step "Resolving / creating execution role: $ROLE_NAME"
if aws iam get-role --role-name "$ROLE_NAME" --profile "$PROFILE" >/dev/null 2>&1; then
  echo "Role exists."
else
  TRUST_POLICY='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
  aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$TRUST_POLICY" \
    --profile "$PROFILE" >/dev/null
  aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" \
    --profile "$PROFILE"
  echo "Role created. Waiting 10s for IAM propagation..."
  sleep 10
fi

ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --profile "$PROFILE" --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"

step "Generating proxy secret"
SECRET=$(openssl rand -hex 24)
echo "Secret: $SECRET"

step "Creating / updating function"
if aws lambda get-function --function-name "$FN_NAME" --region "$REGION" --profile "$PROFILE" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --region "$REGION" --function-name "$FN_NAME" \
    --zip-file "fileb://$ZIP_PATH" --profile "$PROFILE" >/dev/null
  aws lambda update-function-configuration \
    --region "$REGION" --function-name "$FN_NAME" \
    --environment "Variables={PROXY_SECRET=$SECRET,FETCH_TIMEOUT_SECONDS=25}" \
    --timeout 30 --memory-size 256 --profile "$PROFILE" >/dev/null
  echo "Function updated."
else
  aws lambda create-function \
    --region "$REGION" \
    --function-name "$FN_NAME" \
    --runtime "python3.12" \
    --handler "handler.handler" \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$ZIP_PATH" \
    --timeout 30 \
    --memory-size 256 \
    --environment "Variables={PROXY_SECRET=$SECRET,FETCH_TIMEOUT_SECONDS=25}" \
    --profile "$PROFILE" >/dev/null
  echo "Function created."
fi

step "Ensuring Function URL exists"
if URL_OUT=$(aws lambda get-function-url-config --region "$REGION" --function-name "$FN_NAME" --profile "$PROFILE" 2>/dev/null); then
  FUNCTION_URL=$(echo "$URL_OUT" | grep -o 'https://[a-z0-9]*\.lambda-url\.[a-z0-9-]*\.on\.aws/')
else
  URL_OUT=$(aws lambda create-function-url-config \
    --region "$REGION" --function-name "$FN_NAME" \
    --auth-type "NONE" --profile "$PROFILE")
  FUNCTION_URL=$(echo "$URL_OUT" | grep -o 'https://[a-z0-9]*\.lambda-url\.[a-z0-9-]*\.on\.aws/')
  # Allow public invoke (auth is via header secret, not IAM)
  aws lambda add-permission \
    --region "$REGION" --function-name "$FN_NAME" \
    --statement-id "FunctionURLAllowPublic" \
    --action "lambda:InvokeFunctionUrl" \
    --principal "*" --function-url-auth-type "NONE" \
    --profile "$PROFILE" >/dev/null 2>&1 || true
fi

echo
echo "════════════════════════════════════════════════════════"
echo "DONE. Add these to EC2 /opt/collectors/.env:"
echo
echo "  JP_PROXY_URL=$FUNCTION_URL"
echo "  JP_PROXY_SECRET=$SECRET"
echo
echo "Then: sudo systemctl restart collectai-bake"
echo "════════════════════════════════════════════════════════"
