#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";

const root = process.cwd();

const requiredPaths = [
  ".agents/skills/impeccable/SKILL.md",
  ".codex/agents/impeccable_asset_producer.toml",
  "PRODUCT.md",
  "DESIGN.md",
];

const missing = requiredPaths.filter((relativePath) => {
  return !fs.existsSync(path.join(root, relativePath));
});

const packageJson = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const installedRange = packageJson.devDependencies?.impeccable ?? null;

let latestVersion = null;
try {
  const response = await fetch("https://registry.npmjs.org/impeccable/latest");
  if (response.ok) {
    const metadata = await response.json();
    latestVersion = metadata.version;
  }
} catch {
  // Offline checks should still validate local installation.
}

console.log("Impeccable local setup");
console.log(`- npm package: ${installedRange ?? "missing"}`);
console.log(`- latest npm: ${latestVersion ?? "unavailable"}`);
for (const relativePath of requiredPaths) {
  const status = missing.includes(relativePath) ? "missing" : "ok";
  console.log(`- ${relativePath}: ${status}`);
}

if (missing.length > 0 || !installedRange) {
  process.exitCode = 1;
}
