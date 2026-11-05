import {test,expect} from "@playwright/test";

test("unauthenticated visitors are redirected",async({page})=>{
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading",{name:"Enter the control plane."})).toBeVisible();
});

test("operator can sign in",async({page})=>{
  await page.goto("/login");
  await page.getByLabel("ACCESS ROLE").selectOption("operator");
  await page.getByLabel("PASSWORD").fill(process.env.ROCKSOUL_CONSOLE_OPERATOR_PASSWORD??"test-operator-password");
  const loginResponse=page.waitForResponse(response=>response.url().includes("/api/auth/login")&&response.request().method()==="POST");
  await page.getByRole("button",{name:"AUTHENTICATE"}).click();
  const response=await loginResponse;
  expect(response.status()).toBe(200);
  await expect(page).toHaveURL("http://127.0.0.1:3100/");
  await expect(page.getByRole("heading",{name:"Overview"})).toBeVisible();
  const session=await page.request.get("/api/auth/session");
  expect(await session.json()).toMatchObject({authenticated:true,role:"operator"});
});
