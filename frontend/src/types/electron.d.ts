export interface ElectronAPI {
  apiOrigin: string
  getInfo: () => Promise<{ backendPort: number; platform: string }>
  minimize: () => void
  maximize: () => void
  quit: () => void
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}
