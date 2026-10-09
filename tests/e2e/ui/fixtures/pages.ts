/**
 * Enum for all page query parameters supported in the app.
 * These values correspond to the `page` query parameter used in the URL.
 */
export enum Page {
  ApiKeys = "api-keys",
  Models = "models",
  LlmPlayground = "llm-playground",
  Users = "users",
  Teams = "teams",
  // Administration > Organization, which merged Teams and Projects into one entry.
  Organization = "organization",
  // Administration > Access Control, which merged Users, Access Groups and the audit log.
  AccessControl = "access-control",
  Organizations = "organizations",
  AdminPanel = "admin-panel",
  ApiRef = "api_ref",
  LoggingAndAlerts = "logging-and-alerts",
  Budgets = "budgets",
  Guardrails = "guardrails",
  Agents = "agents",
  Prompts = "prompts",
  TransformRequest = "transform-request",
  RouterSettings = "router-settings",
  UiTheme = "ui-theme",
  CostTracking = "cost-tracking",
  ModelHubTable = "model-hub-table",
  Caching = "caching",
  Logs = "logs",
  McpServers = "mcp-servers",
  SearchTools = "search-tools",
  TagManagement = "tag-management",
  VectorStores = "vector-stores",
  NewUsage = "new_usage",
  Usage = "usage",
  Ledger = "ledger",
  Attribution = "attribution",
}
