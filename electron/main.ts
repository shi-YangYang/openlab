import { app, BrowserWindow, ipcMain } from 'electron'
import { spawn, spawnSync, ChildProcess } from 'child_process'
import * as path from 'path'
import * as fs from 'fs'
import * as http from 'http'

let backendProcess: ChildProcess | null = null
let backendPort = 8001
let restartCount = 0
let isRestarting = false
let isQuitting = false
const MAX_RESTARTS = 3

const isDev = !app.isPackaged

function getBackendCommand(): { cmd: string; args: string[]; cwd: string } {
  if (isDev) {
    // Development: use venv uvicorn with --reload
    const backendDir = path.join(app.getAppPath(), 'backend')
    const venvPython = path.join(backendDir, '.venv', 'Scripts', 'python.exe')
    return {
      cmd: venvPython,
      args: ['-m', 'uvicorn', 'app.main:app', '--reload', '--port', String(backendPort)],
      cwd: backendDir,
    }
  }
  // Production: use PyInstaller-packed exe
  const resourcesPath = process.resourcesPath || path.dirname(app.getPath('exe'))
  const backendExe = path.join(resourcesPath, 'openlab-backend', 'openlab-backend.exe')
  return {
    cmd: backendExe,
    args: ['--port', String(backendPort)],
    cwd: path.dirname(backendExe),
  }
}

function killBackend() {
  if (backendProcess && backendProcess.pid) {
    try {
      // Windows: kill the process tree (synchronous so the backend is
      // guaranteed dead before the app process exits).
      spawnSync('taskkill', ['/PID', String(backendProcess.pid), '/T', '/F'])
    } catch {
      // ignore
    }
    backendProcess = null
  }
}

function startBackend(): void {
  const { cmd, args, cwd } = getBackendCommand()
  console.log(`Starting backend: ${cmd} ${args.join(' ')}`)
  backendProcess = spawn(cmd, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  })
  backendProcess.stdout?.on('data', (d: Buffer) => console.log(`[backend] ${d.toString().trim()}`))
  backendProcess.stderr?.on('data', (d: Buffer) => console.error(`[backend:err] ${d.toString().trim()}`))
  backendProcess.on('error', (err) => {
    console.error(`Failed to start backend: ${err.message}`)
    backendProcess = null
  })
  backendProcess.on('exit', (code) => {
    console.log(`Backend exited with code ${code}`)
    backendProcess = null
    if (!isQuitting && code !== 0) {
      void attemptBackendRestart(`Backend crashed with exit code ${code}`)
    }
  })
}

function pollHealth(): Promise<boolean> {
  return new Promise((resolve) => {
    const url = `http://localhost:${backendPort}/api/health`
    const req = http.get(url, (res) => {
      resolve(res.statusCode === 200)
      res.resume()
    })
    req.on('error', () => resolve(false))
    req.setTimeout(2000, () => {
      req.destroy()
      resolve(false)
    })
  })
}

async function waitForBackend(maxWaitMs = 30000): Promise<boolean> {
  const start = Date.now()
  while (Date.now() - start < maxWaitMs) {
    if (await pollHealth()) return true
    await new Promise((r) => setTimeout(r, 500))
  }
  return false
}

async function attemptBackendRestart(reason: string): Promise<void> {
  if (isRestarting || isQuitting) return
  isRestarting = true
  try {
    if (restartCount >= MAX_RESTARTS) {
      console.error(`Backend failed ${MAX_RESTARTS} restart attempts; stopping auto-restart`)
      mainWindow?.webContents.send('electron:backend-error', {
        message: `后端进程已连续 ${MAX_RESTARTS} 次重启失败，已停止自动重启。请关闭应用后重新打开。`,
      })
      return
    }
    restartCount++
    console.log(`${reason}; restarting backend (attempt ${restartCount}/${MAX_RESTARTS})`)
    killBackend()
    startBackend()
    const ok = await waitForBackend()
    if (ok) {
      console.log('Backend restart succeeded; resetting restart counter')
      restartCount = 0
    } else {
      await attemptBackendRestart('Backend still unhealthy after restart')
    }
  } finally {
    isRestarting = false
  }
}

async function findAvailablePort(): Promise<number> {
  let port = 8001
  while (port < 8020) {
    const ok = await new Promise<boolean>((resolve) => {
      const req = http.get(`http://localhost:${port}/api/health`, (res) => {
        resolve(true)
        res.resume()
      })
      req.on('error', () => resolve(false))
      req.setTimeout(1000, () => {
        req.destroy()
        resolve(false)
      })
    })
    // If nothing responds, the port is likely free
    if (!ok) {
      // Double-check with a TCP bind test
      const net = await import('net')
      const free = await new Promise<boolean>((resolve) => {
        const server = net.default.createServer()
        server.once('error', () => resolve(false))
        server.once('listening', () => {
          server.close(() => resolve(true))
        })
        server.listen(port)
      })
      if (free) return port
    }
    port++
  }
  return 8001 // fallback
}

let mainWindow: BrowserWindow | null = null

function createWindow() {
  const iconPath = path.join(app.getAppPath(), 'docs', 'logo.ico')
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1000,
    minHeight: 600,
    frame: false,
    ...(fs.existsSync(iconPath) ? { icon: iconPath } : {}),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  if (isDev) {
    mainWindow.loadURL('http://localhost:5174')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(app.getAppPath(), 'frontend', 'dist', 'index.html'))
  }

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

app.whenReady().then(async () => {
  backendPort = await findAvailablePort()
  process.env.OPENLAB_PORT = String(backendPort)

  startBackend()
  const ready = await waitForBackend()
  if (!ready) {
    await attemptBackendRestart('Backend failed to become healthy on startup')
  }

  // IPC handlers
  ipcMain.on('electron:get-api-origin', (event) => {
    event.returnValue = `http://localhost:${backendPort}`
  })
  ipcMain.handle('electron:getInfo', () => ({
    backendPort,
    platform: process.platform,
  }))
  ipcMain.on('electron:minimize', () => {
    mainWindow?.minimize()
  })
  ipcMain.on('electron:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow?.unmaximize()
    } else {
      mainWindow?.maximize()
    }
  })
  ipcMain.on('electron:quit', () => {
    app.quit()
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  isQuitting = true
  killBackend()
  app.quit()
})

app.on('before-quit', () => {
  isQuitting = true
  killBackend()
})
