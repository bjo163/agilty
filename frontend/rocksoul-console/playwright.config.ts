import {defineConfig,devices} from "@playwright/test";
export default defineConfig({
 testDir:"./e2e",
 fullyParallel:true,
 reporter:"list",
 use:{baseURL:"http://127.0.0.1:3100",trace:"retain-on-failure"},
 webServer:{
  command:"npm run start",
  url:"http://127.0.0.1:3100/login",
  reuseExistingServer:!process.env.CI,
  timeout:120000,
  env:{PORT:"3100",HOSTNAME:"127.0.0.1"}
 },
 projects:[{name:"chromium",use:{...devices["Desktop Chrome"]}}]
});
