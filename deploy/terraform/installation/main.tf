locals {
  name = "tokeniq-${var.customer_key}"

  tags = merge(var.tags, {
    Application = "tokeniq"
    Customer    = var.customer_key
  })
}

resource "aws_cloudwatch_log_group" "installation" {
  name              = "/tokeniq/${var.customer_key}"
  retention_in_days = var.log_retention_days
  tags              = local.tags
}

resource "aws_ecs_task_definition" "installation" {
  family                   = local.name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.execution_role_arn
  task_role_arn            = var.task_role_arn
  tags                     = local.tags

  container_definitions = jsonencode([
    {
      name      = "tokeniq"
      image     = var.image
      essential = true

      portMappings = [{
        containerPort = var.container_port
        protocol      = "tcp"
      }]

      # Both arrive by reference rather than value, so a secret is never in the task
      # definition, in Terraform state, or readable from the console.
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = var.database_url_secret_arn
        },
        {
          name      = "TOKEN_IQ_MASTER_KEY"
          valueFrom = var.master_key_secret_arn
        },
      ]

      environment = [
        {
          name  = "TOKEN_IQ_INSTALLATION"
          value = var.customer_key
        },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.installation.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "tokeniq"
        }
      }
    }
  ])
}

data "aws_region" "current" {}

resource "aws_lb_target_group" "installation" {
  name        = substr(local.name, 0, 32)
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  tags        = local.tags

  health_check {
    path                = "/health/readiness"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }
}

resource "aws_lb_listener_rule" "installation" {
  listener_arn = var.listener_arn
  priority     = var.listener_rule_priority
  tags         = local.tags

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.installation.arn
  }

  # Host-based, so every installation shares one load balancer. A rule per customer costs
  # nothing, where a load balancer per customer is the largest fixed cost of a small account.
  condition {
    host_header {
      values = [var.hostname]
    }
  }
}

resource "aws_ecs_service" "installation" {
  name            = local.name
  cluster         = var.cluster_arn
  task_definition = aws_ecs_task_definition.installation.arn
  desired_count   = 1
  launch_type     = "FARGATE"
  tags            = local.tags

  # One task. The product holds scheduler state in process and guards itself to a single
  # replica, so a second task would not share the work, it would duplicate it.
  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = var.task_security_group_ids
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.installation.arn
    container_name   = "tokeniq"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener_rule.installation]
}
