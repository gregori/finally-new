import { test, expect, Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Wait until at least one watchlist price span is visible.
 * Price spans use the Tailwind 'tabular-nums' class — preserved in production builds.
 */
async function waitForPrices(page: Page): Promise<void> {
  await expect(page.locator('span.tabular-nums').first()).toBeVisible({ timeout: 15_000 });
}

/** Parse a dollar-formatted string to a number ("$10,234.56" → 10234.56). */
function parseDollar(text: string | null): number {
  return parseFloat((text ?? '0').replace(/[$,]/g, ''));
}

/**
 * Get the value div next to a header label in the portfolio stats bar.
 * Structure: <div><div>Label</div><div>$value</div></div>
 */
function headerValue(page: Page, label: string) {
  return page.getByText(label, { exact: true }).locator('..').locator('div').last();
}

// ---------------------------------------------------------------------------
// 1. Fresh start
// ---------------------------------------------------------------------------

test('fresh start — page loads with default state', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle(/FinAlly/);

  await waitForPrices(page);

  // Portfolio header shows ~$10,000
  const portfolioText = await headerValue(page, 'Portfolio').textContent();
  const portfolioValue = parseDollar(portfolioText);
  expect(portfolioValue).toBeGreaterThan(9_000);
  expect(portfolioValue).toBeLessThan(12_000);

  // Cash balance is positive (may be < $10,000 if prior tests ran trades against shared DB)
  const cashText = await headerValue(page, 'Cash').textContent();
  const cash = parseDollar(cashText);
  expect(cash).toBeGreaterThan(0);
  expect(cash).toBeLessThanOrEqual(10_000);

  // Connection status dot has title="connected" once SSE is up
  await expect(page.locator('[title="connected"]')).toBeVisible({ timeout: 10_000 });

  // Default watchlist tickers visible
  for (const ticker of ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']) {
    await expect(page.getByText(ticker).first()).toBeVisible();
  }

  // Price spans are non-zero
  const priceEls = page.locator('span.tabular-nums');
  const count = await priceEls.count();
  expect(count).toBeGreaterThan(0);
  expect(parseDollar(await priceEls.first().textContent())).toBeGreaterThan(0);
});

// ---------------------------------------------------------------------------
// 2. Watchlist management
// ---------------------------------------------------------------------------

test('watchlist — add valid ticker appears in list', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  await page.getByPlaceholder('Add ticker...').fill('PYPL');
  await page.getByRole('button', { name: '+' }).click();

  await expect(page.getByText('PYPL').first()).toBeVisible({ timeout: 8_000 });
});

test('watchlist — adding duplicate ticker shows error', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  // AAPL is already in the default watchlist
  await page.getByPlaceholder('Add ticker...').fill('AAPL');
  await page.getByRole('button', { name: '+' }).click();

  // Backend returns: "AAPL is already in your watchlist"
  await expect(page.getByText(/already/i).first()).toBeVisible({ timeout: 5_000 });
});

test('watchlist — adding invalid ticker shows error', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  // 6-char ticker — backend rejects with "Unknown ticker: XXXXXX"
  await page.getByPlaceholder('Add ticker...').fill('XXXXXX');
  await page.getByRole('button', { name: '+' }).click();

  await expect(page.getByText(/unknown/i).first()).toBeVisible({ timeout: 5_000 });
});

test('watchlist — remove ticker disappears from list', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  // Add UBER first so we can remove a non-default ticker
  await page.getByPlaceholder('Add ticker...').fill('UBER');
  await page.getByRole('button', { name: '+' }).click();
  await expect(page.getByText('UBER').first()).toBeVisible({ timeout: 8_000 });

  // Hover the UBER row to reveal the ✕ button (group-hover:opacity-100)
  const uberRow = page
    .locator('div.group')
    .filter({ has: page.getByText('UBER', { exact: true }) })
    .first();
  await uberRow.hover();
  await uberRow.getByRole('button', { name: '✕' }).click();

  await expect(page.getByText('UBER', { exact: true })).toHaveCount(0, { timeout: 8_000 });
});

// ---------------------------------------------------------------------------
// 3. Buy trade
// ---------------------------------------------------------------------------

test('trade — buy shares reduces cash and creates position', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  const cashBefore = parseDollar(await headerValue(page, 'Cash').textContent());

  await page.getByPlaceholder('Ticker', { exact: true }).fill('AAPL');
  await page.getByPlaceholder('Qty').fill('1');
  await page.getByRole('button', { name: 'BUY' }).click();

  await expect(page.getByText(/BUY.*executed/i)).toBeVisible({ timeout: 10_000 });

  // Give portfolio a moment to refresh
  await page.waitForTimeout(2_000);
  const cashAfter = parseDollar(await headerValue(page, 'Cash').textContent());
  expect(cashAfter).toBeLessThan(cashBefore);

  // AAPL row appears in positions table
  await expect(page.locator('tr').filter({ hasText: 'AAPL' }).first()).toBeVisible({
    timeout: 8_000,
  });
});

// ---------------------------------------------------------------------------
// 4. Sell trade
// ---------------------------------------------------------------------------

test('trade — sell shares increases cash and updates position', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  // Buy 2 shares first
  await page.getByPlaceholder('Ticker', { exact: true }).fill('AAPL');
  await page.getByPlaceholder('Qty').fill('2');
  await page.getByRole('button', { name: 'BUY' }).click();
  await expect(page.getByText(/BUY.*executed/i)).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(1_500);
  const cashAfterBuy = parseDollar(await headerValue(page, 'Cash').textContent());

  // Sell 1 share
  await page.getByPlaceholder('Ticker', { exact: true }).fill('AAPL');
  await page.getByPlaceholder('Qty').fill('1');
  await page.getByRole('button', { name: 'SELL' }).click();
  await expect(page.getByText(/SELL.*executed/i)).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(2_000);
  const cashAfterSell = parseDollar(await headerValue(page, 'Cash').textContent());
  expect(cashAfterSell).toBeGreaterThan(cashAfterBuy);

  // Position row still exists (1 share remaining)
  await expect(page.locator('tr').filter({ hasText: 'AAPL' }).first()).toBeVisible({
    timeout: 8_000,
  });
});

// ---------------------------------------------------------------------------
// 5. Chat with AI
// ---------------------------------------------------------------------------

test('chat — sends message and receives response', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  await page.getByPlaceholder('Ask FinAlly anything... (Enter to send)').fill(
    'What is my portfolio worth?'
  );
  await page.getByRole('button', { name: 'Send' }).click();

  // Mock response: "I've analyzed your portfolio and it looks well-diversified."
  // For non-mock mode any response should contain portfolio-related text
  await expect(page.getByText(/analyzed your portfolio/i).first()).toBeVisible({
    timeout: 15_000,
  });
});

// ---------------------------------------------------------------------------
// 6. Portfolio visualizations
// ---------------------------------------------------------------------------

test('portfolio visualizations — heatmap and P&L chart are visible', async ({ page }) => {
  await page.goto('/');
  await waitForPrices(page);

  // Buy a share to ensure a position exists (earlier tests may have already bought)
  await page.getByPlaceholder('Ticker', { exact: true }).fill('AAPL');
  await page.getByPlaceholder('Qty').fill('1');
  await page.getByRole('button', { name: 'BUY' }).click();
  await expect(page.getByText(/BUY.*executed/i)).toBeVisible({ timeout: 10_000 });

  await page.waitForTimeout(2_000);

  // Heatmap section is visible and shows AAPL
  await expect(page.getByText('Portfolio Heatmap')).toBeVisible();
  await expect(page.locator('svg text').filter({ hasText: 'AAPL' }).first()).toBeVisible();

  // P&L chart section heading is visible
  await expect(page.getByText('Portfolio P&L')).toBeVisible();
});

// ---------------------------------------------------------------------------
// 7. Health check API
// ---------------------------------------------------------------------------

test('api — /api/health returns 200 with success:true', async ({ request }) => {
  const res = await request.get('/api/health');
  expect(res.status()).toBe(200);
  const body = await res.json();
  expect(body.success).toBe(true);
  expect(body.data?.status).toBe('ok');
});
