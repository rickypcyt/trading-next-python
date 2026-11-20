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
        // Con `uvicorn --reload` en Windows, el dueño reportado del puerto puede estar ya muerto
        // mientras su hijo huérfano sigue ocupando el socket. Matamos también a los hijos directos.
        const children = execSync(
          `powershell -Command "Get-CimInstance Win32_Process -Filter 'ParentProcessId=${pid}' | Select-Object -ExpandProperty ProcessId"`,
          { encoding: 'utf8' }
        )
          .split(/\r?\n/)
          .map(line => line.trim())
          .filter(line => /^\d+$/.test(line));

        for (const target of [...children, pid]) {
          try {
            execSync(`taskkill /F /T /PID ${target}`, { stdio: 'ignore' });
            console.log(`Killed process ${target} (port ${port}${target === pid ? '' : `, child of ${pid}`})`);
          } catch {
            // ya estaba cerrado
          }
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

// Dar un momento a Windows para liberar los sockets antes de que arranque el servidor.
await new Promise(resolve => setTimeout(resolve, 1000));
