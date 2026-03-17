import { expect, test } from "@playwright/test";

test("start run, observe transitions, open report, and run again", async ({ page, context }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Resell Intelligence Console" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start run" })).toBeVisible();

  await page.getByRole("button", { name: "Start run" }).click();

  await expect(page.getByRole("button", { name: "Run in progress" })).toBeVisible();
  await expect(page.getByText("Running").first()).toBeVisible();

  await expect(page.getByText("Completed").first()).toBeVisible({ timeout: 60_000 });
  const reportLink = page.getByRole("link", { name: "Open full analyzed-items report" });
  await expect(reportLink).toBeVisible({ timeout: 60_000 });

  const [reportPage] = await Promise.all([
    context.waitForEvent("page"),
    reportLink.click(),
  ]);
  await reportPage.waitForLoadState("domcontentloaded");
  await expect(reportPage).toHaveURL(/api\/artifact\/file/);
  await reportPage.close();

  await expect(page.getByRole("button", { name: "Start run" })).toBeVisible();
  await page.getByRole("button", { name: "Start run" }).click();
  await expect(page.getByRole("button", { name: "Run in progress" })).toBeVisible();
  await expect(page.getByText("Completed").first()).toBeVisible({ timeout: 60_000 });
});
