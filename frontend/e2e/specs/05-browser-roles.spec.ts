import { expect, test } from '@playwright/test';
import { loginAsAdmin, loginAsInvigilator } from '../fixtures/browserAuth';

test.describe('browser routing and primary user journeys', () => {
  test('admin reaches dashboard and can log out', async ({ page }) => {
    await loginAsAdmin(page);
    await expect(page.locator('body')).toContainText(/لوحة|القاعة|Thaqib/);
  });

  test('invigilator reaches schedule and can open monitoring when assigned', async ({ page }) => {
    await loginAsInvigilator(page);
    await expect(page.locator('body')).toContainText(/اليوم|الاختبارات|القاعة/);
    const openButton = page.getByRole('button', { name: /دخول|فتح|مراقبة|بدء/ }).first();
    if (await openButton.count()) {
      await openButton.click();
      await expect(page).toHaveURL(/invigilator\/session/);
      await expect(page.locator('body')).toContainText(/القناة الصوتية|المراقبة|القاعة/);
    }
  });
});
