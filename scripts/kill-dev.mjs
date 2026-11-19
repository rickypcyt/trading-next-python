#!/usr/bin/env node
/**
 * Mata los procesos de desarrollo del frontend (Next.js) y backend (uvicorn).
 * Compatible con Windows (PowerShell) y Unix-like.
 */
import { execSync } from 'node:child_process';

const ports = [3000, 5000];
const isWin = process.platform === 'win32';

for (const port of ports) {
  try {
    if (isWin) {
      const pids = execSync(
        `powershell -Command "Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"`,
        { encoding: 'utf8' }
      )
        .split(/\r?\n/)
        .map(line => line.trim())
        .filter(line => /^\d+$/.test(line));

      for (const pid of [...new Set(pids)]) {
        try {
          execSync(`taskkill /F /PID ${pid}`);
          console.log(`Killed process ${pid} on port ${port}`);
        } catch {
          // ignore already closed
        }
      }
    } else {
      execSync(`lsof -ti:${port} | xargs kill -9 2>/dev/null || true`, { shell: '/bin/sh' });
      console.log(`Killed processes on port ${port}`);
    }
  } catch (err) {
    console.error(`Could not kill port ${port}:`, err.message);
  }
}
