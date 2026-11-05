import {test,expect} from "@playwright/test";

test("unauthenticated visitors are redirected and cannot approve WorkItems",async({page})=>{
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading",{name:"Enter the control plane."})).toBeVisible();
  const approval=await page.request.post("/api/approvals/untrusted-work",{data:{decision:"approved"}});
  expect(approval.status()).toBe(403);
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
  await page.getByRole("button",{name:"Work & evidence"}).click();
  await expect(page.getByRole("heading",{name:"Work & evidence"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Work contracts"})).toBeVisible();
  await expect(page.getByRole("heading",{name:"Verifier profiles & artifact evidence"})).toBeVisible();
  await expect(page.getByRole("button",{name:"CREATE WORK ITEM"})).toBeDisabled();
  await expect(page.getByRole("button",{name:"REGISTER IMMUTABLE PROFILE"})).toBeDisabled();
  await expect(page.getByRole("button",{name:"VERIFY ARTIFACT"})).toBeDisabled();
  const session=await page.request.get("/api/auth/session");
  expect(await session.json()).toMatchObject({authenticated:true,role:"operator"});
});
