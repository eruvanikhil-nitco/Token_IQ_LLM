import { test, expect, type Locator, type Page as PlaywrightPage } from "@playwright/test";
import { ADMIN_STORAGE_PATH } from "../../constants";
import { navigateToPage, dismissFeedbackPopup } from "../../helpers/navigation";
import { Page } from "../../fixtures/pages";

/**
 * Walks each Token IQ screen cold and asserts the sentence that says what its figures mean is on
 * screen before any control is touched.
 *
 * Every other defect in these screens is visible: a tab in the wrong place looks wrong, a uuid
 * where a name belongs looks wrong, an empty state with no way out looks wrong. A sentence that
 * says "your total spend" over a provider figure and a gateway figure looks right, reads well, and
 * teaches the reader to count the same request twice. It is the one thing here that gets more
 * convincing the better it is written, so a browser asserts it rather than a reviewer reading it.
 *
 * These assertions need no traffic, and that is the point: the claim belongs to the screen, not to
 * its data, so a reader who arrives before anything has been ingested is still told what they are
 * about to look at. The arithmetic the claims describe is asserted where it can be made
 * deterministic, in the component tests beside each view.
 */

const claim = (page: PlaywrightPage, phrase: RegExp): Locator => page.getByText(phrase).first();

async function open(page: PlaywrightPage, which: Page): Promise<void> {
  await navigateToPage(page, which);
  await dismissFeedbackPopup(page);
}

test.describe("Every screen says what its figures mean", () => {
  test.use({ storageState: ADMIN_STORAGE_PATH });

  test("Usage opens on Combined, on the view that reconciles the sources", async ({ page }) => {
    await open(page, Page.NewUsage);

    // Combined is first because it is the only view that puts the two sources against each other;
    // Gateway and APIs each show one source alone. It used to open on a view with no data.
    await expect(page.getByRole("tab", { name: "Combined", selected: true })).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole("tab", { name: "Cost Explorer", selected: true })).toBeVisible();
  });

  test("the Cost Explorer says its two columns do add up, which no other screen may say", async ({ page }) => {
    await open(page, Page.NewUsage);

    const explorer = claim(page, /Who the spend belongs to/);
    await expect(explorer).toBeVisible({ timeout: 30_000 });
    await expect(explorer).toContainText("add up to that group's spend");
  });

  test("Source Comparison says the opposite, above the figures rather than under them", async ({ page }) => {
    await open(page, Page.NewUsage);
    await page.getByRole("tab", { name: "Source Comparison" }).click();

    const explanation = claim(page, /never added together/);
    await expect(explanation).toBeVisible({ timeout: 30_000 });

    // Above the figures: a reader who stops at the first number has already been told. Playwright
    // has no document-order matcher, so the rendered boxes are compared instead.
    const figure = page.getByText("Providers billed", { exact: true }).first();
    await expect(figure).toBeVisible();
    const [explanationBox, figureBox] = [await explanation.boundingBox(), await figure.boundingBox()];
    expect(explanationBox, "the explanation is not rendered").not.toBeNull();
    expect(figureBox, "the provider total is not rendered").not.toBeNull();
    expect(explanationBox!.y).toBeLessThan(figureBox!.y);
  });

  test("the APIs tab says these are the provider's own figures", async ({ page }) => {
    await open(page, Page.NewUsage);
    await page.getByRole("tab", { name: "APIs" }).click();

    // Either the claim, or the plain sentence that this build reads no billing API at all. One of
    // the two is always true of this tab, and a blank panel is neither.
    await expect(claim(page, /what the provider itself reported|reads no provider billing APIs/i)).toBeVisible({
      timeout: 30_000,
    });
  });

  test("the Cost Ledger says why the gateway's own records are not in it", async ({ page }) => {
    await open(page, Page.Ledger);

    const ledger = claim(page, /Every cost line the provider reported/);
    await expect(ledger).toBeVisible({ timeout: 30_000 });
    await expect(ledger).toContainText("count it twice");
  });

  test("Bill Reconciliation says the invoice and the ledger are never added", async ({ page }) => {
    await open(page, Page.Ledger);
    await page.getByRole("tab", { name: "Bill Reconciliation" }).click();

    await expect(claim(page, /never added together/)).toBeVisible({ timeout: 30_000 });
  });

  test("Attribution Rules says what a rule does before asking for one", async ({ page }) => {
    await open(page, Page.Attribution);

    await expect(claim(page, /A rule says which team, project or user owns a provider account/)).toBeVisible({
      timeout: 30_000,
    });
  });

  test("Source Comparison never labels anything the total of its two sources", async ({ page }) => {
    await open(page, Page.NewUsage);
    await page.getByRole("tab", { name: "Source Comparison" }).click();

    // The counting rule as a reader meets it. This screen shows the provider figure, the gateway
    // figure and the difference, so a fourth figure labelled as a total of the first two would be
    // the double count. Scoped to this panel: the provider's own total is a fair label elsewhere.
    const panel = page.getByRole("tabpanel", { name: "Source Comparison" });
    await expect(panel.getByText("Providers billed", { exact: true })).toBeVisible({ timeout: 30_000 });
    await expect(panel.getByText(/total spend/i)).toHaveCount(0);
  });
});
