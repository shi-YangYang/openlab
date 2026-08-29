import { contextBridge, ipcRenderer } from 'electron'

// Resolved synchronously at preload time so the renderer can build API URLs
// before its first fetch (the page is loaded via file:// in production).
const apiOrigin = (ipcRenderer.sendSync('electron:get-api-origin') as string | undefined) ?? ''

contextBridge.exposeInMainWorld('electronAPI', {
  apiOrigin,
  getInfo: () => ipcRenderer.invoke('electron:getInfo'),
  minimize: () => ipcRenderer.send('electron:minimize'),
  maximize: () => ipcRenderer.send('electron:maximize'),
  quit: () => ipcRenderer.send('electron:quit'),
})
