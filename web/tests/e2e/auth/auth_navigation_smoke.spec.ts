import { expect, test } from "@playwright/test";
import { TEST_ADMIN_CREDENTIALS } from "@tests/e2e/constants";

test.describe("Authentication navigation smoke", () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
  });

  test("unauthenticated app access redirects to login", async ({ page }) => {
    await page.goto("/app");
    await page.waitForLoadState("networkidle");

    await expect(page).toHaveURL(/\/auth\/login/);
    await expect(page.getByTestId("email")).toBeVisible();
    await expect(page.getByTestId("password")).toBeVisible();
  });

  test("login form establishes a session and opens chat", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("email").fill(TEST_ADMIN_CREDENTIALS.email);
    await page.getByTestId("password").fill(TEST_ADMIN_CREDENTIALS.password);
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page).toHaveURL(/\/app/);
    await expect(page.locator("#onyx-chat-input-textbox")).toBeVisible();

    const me = await page.request.get("/api/me");
    expect(me.ok()).toBe(true);
    const user = await me.json();
    expect(user.email).toBe(TEST_ADMIN_CREDENTIALS.email);
  });

  test("invalid login stays on login and shows an error", async ({ page }) => {
    await page.goto("/auth/login");
    await page.waitForLoadState("networkidle");

    await page.getByTestId("email").fill(TEST_ADMIN_CREDENTIALS.email);
    await page.getByTestId("password").fill("WrongPassword123!");
    await page.getByRole("button", { name: "Sign In" }).click();

    await expect(page.getByText("Invalid email or password", { exact: true })).toBeVisible();
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});
