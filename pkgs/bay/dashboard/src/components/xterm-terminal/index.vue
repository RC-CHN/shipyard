<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'

interface Props {
  shipId: string
  sessionId: string
  token: string
  baseUrl?: string
}

const props = withDefaults(defineProps<Props>(), {
  baseUrl: ''
})

const emit = defineEmits<{
  (e: 'connected'): void
  (e: 'disconnected'): void
  (e: 'error', error: string): void
}>()

const terminalRef = ref<HTMLDivElement | null>(null)
const isConnected = ref(false)
const isConnecting = ref(false)

let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
let ws: WebSocket | null = null
let resizeObserver: ResizeObserver | null = null
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

const getWebSocketUrl = () => {
  // Determine WebSocket URL based on current location
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const host = window.location.host
  
  // Build URL with query parameters
  // 使用 /api 前缀走 Vite 代理（开发模式）或生产模式
  const params = new URLSearchParams({
    token: props.token,
    session_id: props.sessionId,
    cols: String(terminal?.cols || 80),
    rows: String(terminal?.rows || 24),
  })
  
  // 使用 /api 前缀，Vite 会将其代理到后端
  return `${protocol}//${host}/api/ship/${props.shipId}/term?${params.toString()}`
}

const connect = () => {
  if (isConnecting.value || isConnected.value) return
  if (!terminal) return

  isConnecting.value = true
  
  const url = getWebSocketUrl()
  console.log('Connecting to terminal WebSocket:', url)
  
  ws = new WebSocket(url)
  
  ws.onopen = () => {
    isConnected.value = true
    isConnecting.value = false
    terminal?.focus()
    emit('connected')
    console.log('Terminal WebSocket connected')
  }
  
  ws.onmessage = (event) => {
    if (terminal) {
      terminal.write(event.data)
    }
  }
  
  ws.onclose = (event) => {
    isConnected.value = false
    isConnecting.value = false
    emit('disconnected')
    console.log('Terminal WebSocket closed:', event.code, event.reason)
    
    // Auto-reconnect after a delay (unless it was a clean close)
    if (event.code !== 1000 && event.code !== 4001 && event.code !== 4003 && event.code !== 4004) {
      scheduleReconnect()
    }
  }
  
  ws.onerror = (error) => {
    console.error('Terminal WebSocket error:', error)
    emit('error', 'WebSocket connection error')
  }
}

const disconnect = () => {
  if (ws) {
    ws.close(1000)
    ws = null
  }
  isConnected.value = false
  isConnecting.value = false
  
  if (reconnectTimeout) {
    clearTimeout(reconnectTimeout)
    reconnectTimeout = null
  }
}

const scheduleReconnect = () => {
  if (reconnectTimeout) return
  
  reconnectTimeout = setTimeout(() => {
    reconnectTimeout = null
    if (!isConnected.value && !isConnecting.value) {
      console.log('Attempting to reconnect...')
      connect()
    }
  }, 3000)
}

const sendResize = () => {
  if (!terminal || !ws || ws.readyState !== WebSocket.OPEN) return
  
  const resizeMsg = JSON.stringify({
    type: 'resize',
    cols: terminal.cols,
    rows: terminal.rows,
  })
  ws.send(resizeMsg)
}

const initTerminal = () => {
  if (!terminalRef.value) return
  
  terminal = new Terminal({
    cursorBlink: true,
    fontSize: 14,
    fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    theme: {
      background: '#1e1e1e',
      foreground: '#d4d4d4',
      cursor: '#d4d4d4',
      selectionBackground: '#264f78',
      black: '#000000',
      red: '#cd3131',
      green: '#0dbc79',
      yellow: '#e5e510',
      blue: '#2472c8',
      magenta: '#bc3fbc',
      cyan: '#11a8cd',
      white: '#e5e5e5',
      brightBlack: '#666666',
      brightRed: '#f14c4c',
      brightGreen: '#23d18b',
      brightYellow: '#f5f543',
      brightBlue: '#3b8eea',
      brightMagenta: '#d670d6',
      brightCyan: '#29b8db',
      brightWhite: '#e5e5e5',
    },
    allowProposedApi: true,
  })
  
  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  
  terminal.open(terminalRef.value)
  fitAddon.fit()
  
  // Handle terminal input
  terminal.onData((data) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(data)
    }
  })
  
  // Handle terminal resize
  terminal.onResize(() => {
    sendResize()
  })
  
  // Set up ResizeObserver for container resize
  resizeObserver = new ResizeObserver(() => {
    if (fitAddon) {
      fitAddon.fit()
    }
  })
  resizeObserver.observe(terminalRef.value)
  
  // Connect to WebSocket
  connect()
}

const destroyTerminal = () => {
  disconnect()
  
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }
  
  if (terminal) {
    terminal.dispose()
    terminal = null
  }
  
  fitAddon = null
}

// Watch for prop changes that require reconnection
watch([() => props.shipId, () => props.sessionId], () => {
  disconnect()
  nextTick(() => {
    if (terminal) {
      terminal.clear()
      connect()
    }
  })
})

onMounted(() => {
  nextTick(() => {
    initTerminal()
  })
})

onUnmounted(() => {
  destroyTerminal()
})

// Expose methods for parent component
defineExpose({
  connect,
  disconnect,
  isConnected,
})
</script>

<template>
  <div class="xterm-container">
    <div ref="terminalRef" class="xterm-wrapper"></div>
    <div v-if="!isConnected" class="connection-overlay">
      <div v-if="isConnecting" class="connecting">
        <svg class="animate-spin w-6 h-6 text-blue-500" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <span class="ml-2 text-slate-400">连接中...</span>
      </div>
      <div v-else class="disconnected">
        <span class="text-slate-500">已断开连接</span>
        <button @click="connect" class="ml-2 px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded transition-colors">
          重新连接
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.xterm-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
}

.xterm-wrapper {
  width: 100%;
  height: 100%;
  padding: 8px;
}

.xterm-wrapper :deep(.xterm) {
  height: 100%;
}

.xterm-wrapper :deep(.xterm-viewport) {
  overflow-y: auto !important;
}

.xterm-wrapper :deep(.xterm-viewport::-webkit-scrollbar) {
  width: 8px;
}

.xterm-wrapper :deep(.xterm-viewport::-webkit-scrollbar-track) {
  background: #2d2d2d;
}

.xterm-wrapper :deep(.xterm-viewport::-webkit-scrollbar-thumb) {
  background: #555;
  border-radius: 4px;
}

.xterm-wrapper :deep(.xterm-viewport::-webkit-scrollbar-thumb:hover) {
  background: #666;
}

.connection-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(30, 30, 30, 0.9);
  z-index: 10;
}

.connecting,
.disconnected {
  display: flex;
  align-items: center;
}
</style>
