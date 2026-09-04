import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/overview' },
  {
    path: '/overview',
    name: 'overview',
    component: () => import('@/views/Overview.vue'),
    meta: { title: '总览', icon: '📊' },
  },
  {
    path: '/skills',
    name: 'skills',
    component: () => import('@/views/Skills.vue'),
    meta: { title: 'Skill 能力', icon: '🧩' },
  },
  {
    path: '/projects',
    name: 'projects',
    component: () => import('@/views/Projects.vue'),
    meta: { title: '应用与项目', icon: '🗂️' },
  },
  {
    path: '/automation',
    name: 'automation',
    component: () => import('@/views/Placeholder.vue'),
    meta: { title: '自动化任务', icon: '🔄' },
  },
  {
    path: '/wiki',
    name: 'wiki',
    component: () => import('@/views/Placeholder.vue'),
    meta: { title: '知识库', icon: '📚' },
  },
  {
    path: '/system',
    name: 'system',
    component: () => import('@/views/Placeholder.vue'),
    meta: { title: '系统设置', icon: '⚙️' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = `${to.meta.title || ''} · 个人项目工作台`
})

export default router