variable "aws_region" {
  type    = string
  default = "ap-northeast-2" # 서울
}

variable "function_name" {
  type    = string
  default = "edukard"
}

variable "lambda_zip" {
  type        = string
  description = "scripts/build_lambda.sh가 만든 배포 zip 경로"
  default     = "../build/lambda.zip"
}

# --- Slack ---
variable "slack_bot_token" {
  type      = string
  sensitive = true
}

variable "slack_signing_secret" {
  type      = string
  sensitive = true
}

variable "approver_user_id" {
  type = string
}

variable "log_channel_id" {
  type = string
}

# --- Google Sheets ---
variable "google_sheets_id" {
  type = string
}

variable "google_service_account_json" {
  type        = string
  sensitive   = true
  description = "서비스 계정 JSON 키의 전체 내용(문자열). SSM SecureString으로 저장된다."
}
