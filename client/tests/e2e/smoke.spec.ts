import { expect, test } from "@playwright/test";

test("login screen loads with core controls", async ({ page }) => {
  await page.goto("/login");

  await expect(page).toHaveTitle("Login | OpenMynd");
  await expect(
    page.getByRole("heading", { level: 1, name: "Login to OpenMynd" }),
  ).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Login" })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Register here" }),
  ).toBeVisible();

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "Skip to main content" });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeVisible();
});

test("registration screen exposes labelled account controls", async ({ page }) => {
  await page.goto("/register");

  await expect(page).toHaveTitle("Create account | OpenMynd");
  await expect(
    page.getByRole("heading", { level: 1, name: "Create Account" }),
  ).toBeVisible();
  await expect(page.getByLabel("Username")).toHaveAttribute(
    "autocomplete",
    "username",
  );
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "autocomplete",
    "new-password",
  );
});
