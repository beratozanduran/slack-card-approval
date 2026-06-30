data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  # 자기 자신 호출(lazy listener)·로그용 ARN을 변수로 구성해 순환 참조를 피한다.
  function_arn = "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:${var.function_name}"
  ssm_param    = "/${var.function_name}/google-sa-json"
}

# --- Google 서비스 계정 JSON → SSM SecureString ---
resource "aws_ssm_parameter" "google_sa" {
  name   = local.ssm_param
  type   = "SecureString"
  value  = var.google_service_account_json
  tier   = "Standard"
}

# --- IAM 실행 역할 ---
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${var.function_name}-role"
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

data "aws_iam_policy_document" "perms" {
  # CloudWatch Logs
  statement {
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  # SSM에서 SA JSON 읽기 + KMS 복호화
  statement {
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_param}"]
  }
  statement {
    actions   = ["kms:Decrypt"]
    resources = ["*"] # 기본 SSM KMS 키. 전용 키 쓰면 좁히기 권장.
  }
  # lazy listener: 자기 자신을 비동기 재호출
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [local.function_arn]
  }
}

resource "aws_iam_role_policy" "lambda" {
  name   = "${var.function_name}-policy"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.perms.json
}

# --- Lambda 함수 ---
resource "aws_lambda_function" "this" {
  function_name    = var.function_name
  role             = aws_iam_role.lambda.arn
  runtime          = "python3.12"
  handler          = "lambda_handler.handler"
  filename         = var.lambda_zip
  source_code_hash = filebase64sha256(var.lambda_zip)
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      SLACK_BOT_TOKEN      = var.slack_bot_token
      SLACK_SIGNING_SECRET = var.slack_signing_secret
      APPROVER_USER_ID     = var.approver_user_id
      LOG_CHANNEL_ID       = var.log_channel_id
      GOOGLE_SHEETS_ID     = var.google_sheets_id
      GOOGLE_SA_SSM_PARAM  = local.ssm_param
    }
  }
}

# --- Function URL (Slack Request URL) ---
resource "aws_lambda_function_url" "this" {
  function_name      = aws_lambda_function.this.function_name
  authorization_type = "NONE" # Slack 서명(signing secret)으로 검증
}

resource "aws_lambda_permission" "url" {
  statement_id           = "AllowPublicFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}
