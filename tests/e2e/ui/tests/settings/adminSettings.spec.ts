import { test, expect } from "@playwright/test";
import { ADMIN_STORAGE_PATH } from "../../constants";

test.describe("Add Model", () => {
  test.use({ storageState: ADMIN_STORAGE_PATH });

  test("admin settings test", async ({ page }) => {
    await page.goto("/ui");
    // The sidebar is flat: "Admin Settings" is a top-level link, no parent group to expand.
    const sidebar = page.getByRole("complementary");
    await sidebar.getByRole("link", { name: "Admin Settings", exact: true }).click();
    await page.getByRole("tab", { name: "UI Settings" }).click();
    await expect(page.getByText("Configuration for UI-specific")).toBeVisible();
  });
});
