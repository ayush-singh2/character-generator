import {chromium} from '@playwright/test';
const browser = await chromium.launch({headless:true, executablePath:'/usr/bin/chromium'});
const context = await browser.newContext({viewport:{width:1280,height:800}});
const routes = ['/home','/new','/workspace','/character-design?char=ram'];
for (const route of routes) {
  const page = await context.newPage(); const errors=[];
  page.on('pageerror', e => errors.push(`pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  const response = await page.goto(`http://127.0.0.1:4174${route}`, {waitUntil:'domcontentloaded', timeout:15000});
  await page.waitForTimeout(700);
  console.log(JSON.stringify({route,status:response?.status(),title:await page.title(),h1:await page.locator('h1').first().textContent().catch(()=>''),errors,buttons:await page.locator('button').count(),links:await page.locator('a').count()}));
  await page.close();
}
await browser.close();
