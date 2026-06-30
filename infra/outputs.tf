output "function_url" {
  description = "Slack Event Subscriptions / Interactivity Request URL로 등록할 주소"
  value       = aws_lambda_function_url.this.function_url
}

output "function_name" {
  value = aws_lambda_function.this.function_name
}
