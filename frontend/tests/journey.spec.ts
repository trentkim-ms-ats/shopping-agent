import { test, expect, Page } from "@playwright/test";
import type { Reply } from "../lib/types";

// Every shopper decision is a chat turn now, so the tests speak instead of clicking.
async function say(page: Page, text: string) {
  await page.getByLabel("Reply to your trail guide").fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
}

// Products are rendered inline in the conversation; the newest block is the live shortlist.
function shown(page: Page) {
  return page.locator(".chat-items").last().locator("> ol > li");
}

test("each product explains its recommendation in the card without extending the chat", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Reply to your trail guide").fill("Lightweight hiking jacket under $200");
  const replyPromise = page.waitForResponse(response =>
    response.url().endsWith("/messages") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Send message" }).click();
  const reply: Reply = await (await replyPromise).json();
  const cards = shown(page);
  await expect(cards).toHaveCount(3);
  for (const [index, item] of reply.cards.entries()) {
    const explanation = cards.nth(index).locator(".recommendation-reason");
    await expect(explanation.getByRole("heading", { name: "Why we recommend it" })).toBeVisible();
    await expect(explanation).toContainText(item.description);
    await expect(explanation).toContainText("within your $200.00 budget");
    await expect(explanation).toContainText(`Your requested size M is in stock in ${item.variant.color}.`);
    expect(item.match_summary).toBeTruthy();
    await expect(explanation.locator(".match-summary")).toHaveText(item.match_summary!);
  }
  await expect(page.locator(".chat-messages .recommendation-reason")).toHaveCount(3);
  await expect(page.locator(".recommendations")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  await cards.first().scrollIntoViewIfNeeded();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("priority action retries preserve the structured choice and request ID", async ({ page }) => {
  const attempts: { request_id: string; text: string; priority_choice: boolean }[] = [];
  await page.route("**/messages", async route => {
    if (route.request().method() === "POST") {
      const body = route.request().postDataJSON();
      if (body.priority_choice) {
        attempts.push(body);
        if (attempts.length === 1) {
          return route.fulfill({ status: 503, json: {
            error: { code: "MODERATION_UNAVAILABLE", message: "Screening unavailable. Please retry.", retryable: true },
          } });
        }
      }
    }
    await route.fallback();
  });
  await page.goto("/");
  await page.getByRole("button", { name: "I need a jacket for hiking this fall." }).click();
  await page.getByRole("button", { name: "Lightweight", exact: true }).click();
  await expect(page.locator(".error-banner")).toContainText("Screening unavailable");
  await page.getByRole("button", { name: "Retry message", exact: true }).click();
  await expect(shown(page)).toHaveCount(3);
  expect(attempts).toHaveLength(2);
  expect(attempts[1]).toEqual(attempts[0]);
  expect(attempts[0]).toMatchObject({ text: "Lightweight", priority_choice: true });
  await expect(page.locator(".constraints")).toContainText("lightweight");
});

test("color images update asynchronously without blocking chat and retry explicitly", async ({ page }) => {
  const first = "a".repeat(64), second = "b".repeat(64);
  const calls: Record<string, number> = {};
  let retried = false;
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=", "base64");
  await page.route("**/api/product-color-images/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith(".png")) return route.fulfill({ contentType: "image/png", body: png });
    if (path.endsWith("/retry")) {
      retried = true;
      return route.fulfill({ json: { key: second, status: "queued", color: "Black", image_url: null, error: null } });
    }
    const key = path.split("/").pop() || "";
    calls[key] = (calls[key] || 0) + 1;
    const completed = key === second ? retried : calls[key] > 1;
    await route.fulfill({ json: { key, status: completed ? "completed" : "running", color: "Black",
      image_url: completed ? `/api/product-color-images/${key}.png` : null, error: null } });
  });
  await page.route("**/messages", async route => {
    const response = await route.fetch();
    const data = await response.json();
    for (const [i, key] of [first, second].entries()) {
      data.cards[i].image_url = null;
      data.cards[i].color_image = { key, color: "Black", status: i ? "failed" : "queued", image_url: null,
        error: i ? { code: "PROVIDER_UNAVAILABLE", message: "Color edit failed.", retryable: true } : null };
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  await page.getByLabel("Reply to your trail guide").fill("Lightweight hiking jacket");
  await page.getByRole("button", { name: "Send message" }).click();
  const cards = shown(page);
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).getByText("Preparing Black preview…")).toBeVisible();
  await page.getByLabel("Reply to your trail guide").fill("Tell me more about the first");
  await expect(page.getByRole("button", { name: "Send message" })).toBeEnabled();
  await expect(cards.nth(0).locator("img")).toHaveCount(0);
  await cards.nth(1).getByRole("button", { name: "Retry color image" }).click();
  await expect(cards.nth(0).locator("img")).toBeVisible({ timeout: 10000 });
  await expect(cards.nth(1).locator("img")).toBeVisible({ timeout: 10000 });
  await expect(cards.nth(0).getByText("AI illustration · Black · details may differ")).toBeVisible();
  expect(retried).toBe(true);
});

test("catalog art: generated image, explicit error and missing-image silhouette", async ({ page }) => {
  const png = Buffer.from(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=",
    "base64",
  );
  await page.route("**/api/product-images/test-completed.png", route =>
    route.fulfill({ contentType: "image/png", body: png }));
  await page.route("**/api/product-images/test-missing.png", route =>
    route.fulfill({ status: 404, body: "Not found" }));
  await page.route("**/messages", async route => {
    const response = await route.fetch();
    const data = await response.json();
    if (data.cards.length === 3) {
      data.cards[0].image_url = "/api/product-images/test-completed.png";
      data.cards[1].image_url = "/api/product-images/test-missing.png";
      data.cards[2].image_url = null;
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  await page.getByLabel("Reply to your trail guide").fill("Lightweight hiking jacket");
  await page.getByRole("button", { name: "Send message" }).click();
  const cards = shown(page);
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0).locator("img")).toBeVisible();
  await expect.poll(() => cards.nth(0).locator("img").evaluate((image: HTMLImageElement) =>
    image.complete && image.naturalWidth > 0)).toBe(true);
  await expect(cards.nth(0).getByText("AI illustration · color/details may differ")).toBeVisible();
  await expect(cards.nth(1).getByRole("status")).toHaveText("Image unavailable · category illustration");
  await expect(cards.nth(2).getByText("Category illustration", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("attached complement images keep updating after the latest list changes and can retry", async ({ page }) => {
  const first = "c".repeat(64), second = "d".repeat(64);
  let ready = false, retried = false;
  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l9sAAAAASUVORK5CYII=", "base64");
  await page.route("**/api/product-color-images/**", async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith(".png")) return route.fulfill({ contentType: "image/png", body: png });
    if (path.endsWith("/retry")) {
      retried = true;
      return route.fulfill({ json: { key: second, status: "queued", color: "Black", image_url: null, error: null } });
    }
    const key = path.split("/").pop();
    const completed = key === first ? ready : retried;
    await route.fulfill({ json: { key, status: completed ? "completed" : "running", color: "Black",
      image_url: completed ? `/api/product-color-images/${key}.png` : null, error: null } });
  });
  await page.route("**/messages", async route => {
    const response = await route.fetch();
    const data: Reply = await response.json();
    if (data.reply.kind === "selection") {
      for (const [i, key] of [first, second].entries()) {
        data.complements[i].image_url = null;
        data.complements[i].color_image = { key, color: "Black", status: i ? "failed" : "queued",
          image_url: null, error: i ? { code: "PROVIDER_UNAVAILABLE", message: "Color edit failed.", retryable: true } : null };
      }
    }
    await route.fulfill({ response, json: data });
  });
  await page.goto("/");
  await say(page, "Lightweight hiking jacket");
  await say(page, "Choose the first one");
  const attached = page.locator(".chat-items.accent").first().locator("> ol > li");
  await expect(attached).toHaveCount(2);
  await expect(attached.first()).toContainText("Preparing Black preview");
  await expect(attached.nth(1)).toContainText("Color edit failed.");
  await say(page, "Complete my outfit");
  await expect(page.getByRole("heading", { name: "Complementary picks" })).toBeVisible();
  ready = true;
  await expect(attached.first().locator("img")).toHaveAttribute("src", new RegExp(`${first}\\.png$`), { timeout: 10000 });
  await expect(attached.first()).not.toContainText("Preparing");
  await attached.nth(1).getByRole("button", { name: "Retry color image" }).click();
  await expect(attached.nth(1)).toContainText("Preparing Black preview");
  await expect(attached.nth(1).locator("img")).toHaveAttribute("src", new RegExp(`${second}\\.png$`), { timeout: 10000 });
  await expect(attached.nth(1)).not.toContainText("Color edit failed.");
  expect(retried).toBe(true);
});

test("comparison requests explain the missing feature without inventing a table", async ({ page }) => {
  await page.goto("/");
  await say(page, "Lightweight hiking jacket");
  await expect(shown(page)).toHaveCount(3);
  await expect(page.locator(".chat-message.assistant").last()).not.toContainText("ask me to compare");
  await say(page, "Compare the first two");
  await expect(page.locator(".chat-message.assistant").last()).toContainText("not available in this demo");
  await expect(page.locator(".chat-message.assistant").last()).toContainText("Why this match");
  await expect(page.locator(".selection-summary")).toHaveCount(0);
  await expect(shown(page)).toHaveCount(3);
});

test("AT-10: clarification, recommendations, audit, outfit and image", async ({ page }) => {
  const measurementRequests: string[] = [];
  const chatRequests: { text: string; priority_choice: boolean }[] = [];
  page.on("request", request => {
    if (/\/journey(?:\/events)?(?:\?|$)/.test(request.url())) measurementRequests.push(request.url());
    if (request.url().endsWith("/messages") && request.method() === "POST") {
      chatRequests.push(request.postDataJSON());
    }
  });
  await page.goto("/?scoutTheme=light");
  await expect(page.getByText("Replay — simulated API outputs · no live inference")).toBeVisible();
  await page.getByRole("button", { name: "I need a jacket for hiking this fall." }).click();
  await expect(page.getByText("What matters most for your hike?")).toBeVisible();
  await page.getByRole("button", { name: "Light rain protection", exact: true }).click();
  await expect(shown(page)).toHaveCount(3);
  expect(chatRequests.slice(0, 2)).toEqual([
    expect.objectContaining({ text: "I need a jacket for hiking this fall.", priority_choice: false }),
    expect.objectContaining({ text: "Light rain protection", priority_choice: true }),
  ]);
  await expect(page.getByRole("button", { name: "Light rain protection", exact: true })).toBeDisabled();
  await page.getByRole("button", { name: "Why this match" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("20,000 mm waterproof", { exact: true })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await say(page, "Choose the first one");
  await expect(page.locator(".selection-summary li")).toHaveCount(1);
  await say(page, "Complete my outfit");
  await expect(shown(page)).toHaveCount(2);
  await say(page, "Add the first one");
  await expect(page.locator(".selection-summary li")).toHaveCount(2);
  await expect(page.getByLabel("Demo cart: 0 items", { exact: true })).toBeVisible();
  await say(page, "Save this to the demo cart");
  await expect(page.getByText("Saved to demo cart. No purchase or payment.")).toBeVisible();
  await expect(page.getByLabel("Demo cart: 2 items", { exact: true })).toBeVisible();
  await say(page, "Yes, that helped");
  await expect(page.getByText("Thank you — your feedback was recorded.")).toBeVisible();
  await say(page, "Show the try-on preview");
  await expect(page.getByText("AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Replay · static diagram, not GPT-Image output")).toBeVisible();
  expect(measurementRequests).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({ path: "../data/runtime/journey-1280.png", fullPage: true });
});

test("budget changes require review and checked alternatives only change one requirement", async ({ page }) => {
  await page.goto("/");
  await say(page, "Lightweight hiking jacket");
  await say(page, "Choose the first one");
  await say(page, "Save this to the demo cart");
  await expect(page.getByText("Saved to demo cart. No purchase or payment.")).toBeVisible();
  await say(page, "Keep the jacket under $1");
  await expect(page.getByRole("button", { name: /Raise jacket budget to/ })).toBeVisible();
  await expect(page.locator(".preview-block .card-cue")).toContainText("Review your selection");
  await expect(page.locator(".selection-summary .card-cue")).toContainText("keep these exceptions");
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  await say(page, "Keep these exceptions and save to the demo cart");
  await expect(page.getByText("Saved to demo cart. No purchase or payment.")).toBeVisible();
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: /Raise jacket budget to/ }).click();
  await expect(shown(page).first()).toBeVisible();
  await expect(page.locator(".constraints")).toContainText("Size M");
  await expect(page.locator(".constraints")).toContainText("Season fall");
});

test("demo cart counts only validated unique saves and resets with the journey", async ({ page }) => {
  let saveTurns = 0;
  await page.route("**/messages", async route => {
    const body = route.request().postDataJSON();
    if (typeof body?.text === "string" && body.text.includes("demo cart")) {
      saveTurns++;
      if (saveTurns === 1) return route.fulfill({ status: 409, json: {
        error: { code: "UNAVAILABLE_VARIANT", message: "Replace unavailable items before finishing.", retryable: false },
      } });
    }
    await route.fallback();
  });
  await page.goto("/");
  await say(page, "Lightweight hiking jacket");
  await say(page, "Choose the first one");
  await say(page, "Save this to the demo cart");
  await expect(page.locator(".error-banner")).toContainText("Replace unavailable items");
  await expect(page.getByLabel("Demo cart: 0 items", { exact: true })).toBeVisible();
  await expect(page.getByText("Saved to demo cart. No purchase or payment.")).toHaveCount(0);
  await say(page, "Save this to the demo cart");
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  await say(page, "Save this to the demo cart");
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  expect(saveTurns).toBe(3);
  await say(page, "Complete my outfit");
  await say(page, "Add the first one");
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  await say(page, "Save this to the demo cart");
  await expect(page.getByLabel("Demo cart: 2 items", { exact: true })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByRole("button", { name: "Reset journey" }).click();
  await expect(page.getByLabel("Demo cart: 0 items", { exact: true })).toBeVisible();
  await page.getByText("How this recommendation was built", { exact: false }).click();
  await page.getByLabel("Test another synthetic profile").selectOption("sam");
  await expect(page.getByLabel("Demo cart: 0 items", { exact: true })).toBeVisible();
  await say(page, "Lightweight hiking jacket");
  await say(page, "Choose the first one");
  await say(page, "Save this to the demo cart");
  await expect(page.getByLabel("Demo cart: 1 item", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Demo cart: 0 items", { exact: true })).toBeVisible();
});

test("keyboard access and narrow-screen overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByLabel("Reply to your trail guide")).toBeVisible();
  await page.getByLabel("Reply to your trail guide").fill("Lightweight jacket for fall hiking under $200");
  await page.keyboard.press("Tab");
  await page.keyboard.press("Enter");
  await expect(shown(page)).toHaveCount(3);
  await expect(shown(page).last()).toBeInViewport();
  await expect(page.getByRole("region", { name: "Shopping conversation" })).toBeVisible();
  await expect(page.getByLabel("Reply to your trail guide")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("shared-eligibility baseline remains without journey measurements", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Reply to your trail guide").fill("Lightweight hiking jacket under $100");
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(shown(page).first()).toBeVisible();
  await page.getByText("How this recommendation was built", { exact: false }).click();
  await page.getByRole("button", { name: "Search raw catalog" }).click();
  await expect(page.getByText("This is not an enrichment ablation or proof of uplift.", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh journey measurements" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Observed journey — not estimated uplift" })).toHaveCount(0);
  await expect(page.locator(".journey-metrics")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("AT-12: fixed full-body sample, try-on and removal without generating a new person", async ({ page }) => {
  const generationRequests: string[] = [];
  page.on("request", request => {
    if (request.url().includes("/sample-people")) generationRequests.push(request.url());
  });
  await page.goto("/");
  await say(page, "Lightweight hiking jacket");
  await say(page, "Choose the first one");
  await expect(page.locator('input[type="file"]')).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Generate.*sample person/ })).toHaveCount(0);
  const sampleImage = page.getByAltText("Fixed AI-generated fictional adult, full-body demo photo");
  await expect(sampleImage).toBeVisible({ timeout: 15000 });
  const sampleUrl = await sampleImage.getAttribute("src");
  expect(sampleUrl).toContain("/api/demo/sample-person.png");
  await expect(page.getByText("In a real shopping experience, shoppers could upload their own full-body photo", { exact: false })).toBeVisible();
  await expect(page.getByRole("checkbox")).toHaveCount(0);
  await say(page, "Show the try-on preview");
  await expect(page.getByText("AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.", { exact: true })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText("Replay mode: the fixed photo is a pre-generated AI asset", { exact: false })).toBeVisible();
  const image = page.locator(".preview-image img");
  const privateUrl = await image.getAttribute("src");
  expect(privateUrl).toContain("/outfits/");
  await page.getByRole("button", { name: "Remove try-on preview", exact: true }).click();
  await expect(sampleImage).toBeVisible({ timeout: 15000 });
  expect((await page.request.get(privateUrl!)).status()).toBe(404);
  expect((await page.request.get(sampleUrl!)).status()).toBe(200);
  await say(page, "Show the try-on preview");
  await expect(page.getByText("AI virtual try-on — visual reference only; appearance may differ. No size or fit prediction.", { exact: true })).toBeVisible({ timeout: 15000 });
  const replacementUrl = await image.getAttribute("src");
  await page.getByRole("button", { name: "Remove try-on preview" }).click();
  await expect(sampleImage).toBeVisible();
  await expect(page.locator(".preview-block .card-cue")).toContainText("Say “show the try-on preview”");
  expect((await page.request.get(replacementUrl!)).status()).toBe(404);
  expect(generationRequests).toHaveLength(0);
});
