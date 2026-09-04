import { defineStore } from 'pinia'
import { getConfig, startProject, stopProject, projectStatus, openPath } from '@/api'

export const useWorkbenchStore = defineStore('workbench', {
  state: () => ({
    categories: [],
    loading: false,
    refreshing: false,
  }),
  getters: {
    allProjects(state) {
      return state.categories.flatMap(c => c.projects)
    },
    projectCount(state) {
      return state.categories.reduce((n, c) => n + c.projects.length, 0)
    },
  },
  actions: {
    async load() {
      this.loading = true
      try {
        const data = await getConfig()
        this.categories = data.categories
      }
      finally {
        this.loading = false
      }
    },
    async refresh() {
      this.refreshing = true
      try {
        await this.load()
      }
      finally {
        this.refreshing = false
      }
    },
    async start(id) {
      const r = await startProject(id)
      return r
    },
    async stop(id) {
      return await stopProject(id)
    },
    async status(id) {
      return await projectStatus(id)
    },
    async open(id) {
      return await openPath(id)
    },
  },
})