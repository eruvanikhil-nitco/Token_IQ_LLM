output "service_name" {
  description = "The ECS service, which the upgrade tool names when rolling this installation."
  value       = aws_ecs_service.installation.name
}

output "task_definition_arn" {
  description = "The exact task definition running, so a rollback can name the one to go back to."
  value       = aws_ecs_task_definition.installation.arn
}

output "target_group_arn" {
  value = aws_lb_target_group.installation.arn
}

output "log_group" {
  description = "Where this installation's logs go, so support can find one customer without reading the fleet."
  value       = aws_cloudwatch_log_group.installation.name
}
