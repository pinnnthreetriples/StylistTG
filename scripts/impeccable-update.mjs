#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = process.cwd();
const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "impeccable-"));
const repoDir = path.join(tempDir, "repo");

function copyDirectory(source, destination) {
  fs.rmSync(destination, { force: true, recursive: true });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, { recursive: true });
}

try {
  execFileSync(
    "git",
    ["clone", "--depth", "1", "https://github.com/pbakaus/impeccable.git", repoDir],
    { stdio: "inherit" },
  );

  copyDirectory(
    path.join(repoDir, ".agents", "skills", "impeccable"),
    path.join(root, ".agents", "skills", "impeccable"),
  );
  copyDirectory(path.join(repoDir, ".codex", "agents"), path.join(root, ".codex", "agents"));

  console.log("Updated Impeccable project skill and Codex agent files.");
  console.log("Run `npm update impeccable` separately to update the CLI package.");
} finally {
  fs.rmSync(tempDir, { force: true, recursive: true });
}
