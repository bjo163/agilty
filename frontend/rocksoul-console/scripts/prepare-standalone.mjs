import { cpSync, existsSync, mkdirSync } from "node:fs";

const standalone = ".next/standalone";
mkdirSync(`${standalone}/.next`, { recursive: true });

if (existsSync(".next/static")) {
  cpSync(".next/static", `${standalone}/.next/static`, { recursive: true });
}
if (existsSync("public")) {
  cpSync("public", `${standalone}/public`, { recursive: true });
}
