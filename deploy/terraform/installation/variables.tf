# One customer's installation.
#
# Everything expensive is shared and arrives as an input: the network, the Postgres server,
# the load balancer, the cluster. What this module creates is only what must not be shared.

variable "customer_key" {
  description = "The customer's key from the manifest. Becomes the database and role name, so it is lower case letters, digits and underscores."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{2,30}$", var.customer_key))
    error_message = "customer_key must be 3 to 31 characters of lower case letters, digits and underscores, starting with a letter."
  }
}

variable "hostname" {
  description = "The hostname this installation answers on. The shared load balancer routes by it, so it is unique across installations."
  type        = string
}

variable "image" {
  description = "The container image to run. Required, with no default: an installation that cannot say which build it runs should not be created."
  type        = string

  validation {
    condition     = !can(regex(":(latest|main|stable)$", var.image))
    error_message = "Pin the image to a commit hash or a semantic version. A moving tag cannot be rolled back to a known build."
  }
}

variable "cpu" {
  description = "Fargate CPU units, from the manifest's size."
  type        = number
}

variable "memory" {
  description = "Fargate memory in MiB, from the manifest's size."
  type        = number
}

# ---------- Shared infrastructure, passed in ----------

variable "cluster_arn" {
  description = "The shared ECS cluster every installation runs in."
  type        = string
}

variable "private_subnet_ids" {
  description = "Shared private subnets for the task."
  type        = list(string)
}

variable "task_security_group_ids" {
  description = "Security groups for the task, allowing egress and reaching the shared database."
  type        = list(string)
}

variable "listener_arn" {
  description = "The shared load balancer's HTTPS listener. This module adds one host-based rule to it."
  type        = string
}

variable "listener_rule_priority" {
  description = "Priority of this installation's rule on the shared listener. Unique per installation."
  type        = number
}

variable "vpc_id" {
  description = "The shared VPC, for the target group."
  type        = string
}

variable "database_url_secret_arn" {
  description = "Secrets Manager entry holding this customer's own database connection string, created by provisioning."
  type        = string
}

variable "master_key_secret_arn" {
  description = "Secrets Manager entry holding this installation's master key, created by provisioning."
  type        = string
}

variable "execution_role_arn" {
  description = "Shared ECS execution role, which pulls the image and reads the two secrets."
  type        = string
}

variable "task_role_arn" {
  description = "Shared ECS task role for the running container."
  type        = string
}

variable "log_retention_days" {
  description = "How long this installation's logs are kept."
  type        = number
  default     = 30
}

variable "container_port" {
  description = "The port the product listens on inside the container."
  type        = number
  default     = 4000
}

variable "tags" {
  description = "Tags applied to everything this module creates, so one customer's costs can be read off the bill."
  type        = map(string)
  default     = {}
}
