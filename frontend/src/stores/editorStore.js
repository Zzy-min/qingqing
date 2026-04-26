import { create } from 'zustand'

const useEditorStore = create((set, get) => ({
  // Image state
  originalImage: null,
  processedImage: null,

  // UI state
  isProcessing: false,
  activeTab: 'ai', // 'ai' | 'filters' | 'history'

  // History
  history: [],
  historyIndex: -1,

  // Actions
  setOriginalImage: (imageData) => {
    set({ originalImage: imageData })
    get().addToHistory(imageData, null)
  },

  setProcessedImage: (imageData) => {
    set({ processedImage: imageData })
    // Update history with processed result
    const state = get()
    if (state.history.length > 0) {
      const lastEntry = { ...state.history[state.history.length - 1] }
      lastEntry.result = imageData
      const newHistory = [...state.history.slice(0, -1), lastEntry]
      set({ history: newHistory })
    }
  },

  setIsProcessing: (isProcessing) => set({ isProcessing }),

  setActiveTab: (tab) => set({ activeTab: tab }),

  addToHistory: (original, result) => {
    set((state) => {
      const newHistory = [
        ...state.history.slice(0, state.historyIndex + 1),
        { original, result, timestamp: Date.now() }
      ].slice(-20) // Keep last 20
      return {
        history: newHistory,
        historyIndex: newHistory.length - 1
      }
    })
  },

  restoreFromHistory: (index) => {
    const entry = get().history[index]
    if (entry) {
      set({
        originalImage: entry.original,
        processedImage: entry.result,
        historyIndex: index
      })
    }
  },

  reset: () => set({
    originalImage: null,
    processedImage: null,
    isProcessing: false,
    history: [],
    historyIndex: -1
  })
}))

export default useEditorStore
