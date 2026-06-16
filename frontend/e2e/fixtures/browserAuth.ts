import { expect, type Page } from '@playwright/test';
import { env } from './env';

export async function loginInBrowser(page: Page, username: string, password: string): Promise<void> {
  await page.goto('/');
  await page.getByPlaceholder('بريد الكتروني أو اسم المستخدم').fill(username);
  await page.getByPlaceholder('كلمة المرور').fill(password);
  await page.getByRole('button', { name: 'تسجيل الدخول' }).click();
  await expect(page.locator('body')).not.toContainText('خطأ في اسم المستخدم أو كلمة المرور');
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await loginInBrowser(page, env.adminUsername, env.adminPassword);
  await expect(page).toHaveURL(/dashboard/);
}

export async function loginAsInvigilator(page: Page): Promise<void> {
  await loginInBrowser(page, env.invigilatorUsername, env.invigilatorPassword);
  await expect(page).toHaveURL(/invigilator/);
}
