import { expect, test } from "@playwright/test";

test("login screen loads with core controls", async ({ page }) => {
  await page.goto("/login");

  await expect(page.getByText("Login to AI Diary")).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Register here" }),
  ).toBeVisible();
});
