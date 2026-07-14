#!/usr/bin/env bash
# Deploy the minimal MCP to AWS Lambda + API Gateway (HTTP API).
#
# No dependencies => packaging is just zipping two files (no pip, no wheels).
#
# Required env: ROLE_ARN   (a Lambda execution role, e.g. with AWSLambdaBasicExecutionRole)
# Optional env: FUNC (default minimal-mcp), AWS_REGION (default us-east-1)
set -euo pipefail

FUNC=${FUNC:-minimal-mcp}
REGION=${AWS_REGION:-us-east-1}
ROLE_ARN=${ROLE_ARN:?set ROLE_ARN to a Lambda execution role ARN}
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "1) Packaging ..."
rm -f "$DIR/mcp.zip"
( cd "$DIR" && zip -q mcp.zip mcp_core.py lambda_function.py )

echo "2) Create or update the Lambda function ..."
if aws lambda get-function --function-name "$FUNC" --region "$REGION" >/dev/null 2>&1; then
  aws lambda update-function-code --function-name "$FUNC" \
      --zip-file "fileb://$DIR/mcp.zip" --region "$REGION" >/dev/null
else
  aws lambda create-function --function-name "$FUNC" \
      --runtime python3.12 --architectures x86_64 \
      --handler lambda_function.lambda_handler \
      --role "$ROLE_ARN" --timeout 15 --memory-size 128 \
      --zip-file "fileb://$DIR/mcp.zip" --region "$REGION" >/dev/null
fi
aws lambda wait function-updated --function-name "$FUNC" --region "$REGION"

echo "3) Wire an HTTP API with a POST /mcp route ..."
ACCT=$(aws sts get-caller-identity --query Account --output text)
LAMBDA_ARN="arn:aws:lambda:$REGION:$ACCT:function:$FUNC"

API_ID=$(aws apigatewayv2 create-api --name "${FUNC}-api" --protocol-type HTTP \
  --target "$LAMBDA_ARN" --region "$REGION" --query ApiId --output text)

# create-api --target auto-creates a $default route + integration + stage.
aws lambda add-permission --function-name "$FUNC" --region "$REGION" \
  --statement-id apigw-invoke --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:$REGION:$ACCT:$API_ID/*" >/dev/null

ENDPOINT=$(aws apigatewayv2 get-api --api-id "$API_ID" --region "$REGION" \
  --query ApiEndpoint --output text)

echo ""
echo "Deployed. Endpoint: $ENDPOINT/mcp"
echo "Smoke test:"
echo "  curl -s -X POST \"$ENDPOINT/mcp\" -H 'Content-Type: application/json' \\"
echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"initialize\",\"params\":{}}'"
