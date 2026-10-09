import { Page } from "./pages";

/**
 * Maps sidebar menu item labels to their corresponding page enum values.
 * This mapping is for the admin role.
 */
export const menuLabelToPage: Record<string, Page> = {
  "Virtual Keys": Page.ApiKeys,
  Playground: Page.LlmPlayground,
  Models: Page.Models,
  "Models + Endpoints": Page.Models,
  "Cost Explorer": Page.NewUsage,
  Organization: Page.Organization,
  Teams: Page.Teams, // Legacy label support
  "Access Control": Page.AccessControl,
  Users: Page.Users, // Legacy label support
  "Internal User": Page.Users, // Legacy label support
  Organizations: Page.Organizations,
  "API Reference": Page.ApiRef,
  "AI Hub": Page.ModelHubTable,
  "Model Hub": Page.ModelHubTable,
  Logs: Page.Logs,
  Guardrails: Page.Guardrails,
  "Router Settings": Page.RouterSettings,
  "Logging & Alerts": Page.LoggingAndAlerts,
  Settings: Page.Settings,
  "Admin Settings": Page.AdminPanel, // Legacy label support
  "Pricing & Rates": Page.CostTracking,
  "UI Theme": Page.UiTheme,
  "Response Cache": Page.Caching,
  Caching: Page.Caching, // Legacy label support
  Prompts: Page.Prompts,
  "Budgets & Forecasts": Page.Budgets,
  "API Playground": Page.TransformRequest,
  "Tag Management": Page.TagManagement,
  "Classic Usage": Page.Usage,
  "MCP Servers": Page.McpServers,
  "Vector Stores": Page.VectorStores,
};
