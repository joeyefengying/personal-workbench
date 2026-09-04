async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok)
    throw new Error(`请求失败: ${res.status}`)
  return res.json()
}

export function getConfig() {
  return request('/api/config')
}
export function startProject(id) {
  return request(`/api/start/${id}`, { method: 'POST' })
}
export function stopProject(id) {
  return request(`/api/stop/${id}`, { method: 'POST' })
}
export function projectStatus(id) {
  return request(`/api/status/${id}`)
}
export function openPath(id) {
  return request(`/api/open/${id}`, { method: 'POST' })
}
export function getSkills() {
  return request('/api/skills')
}
export function openSkill(payload) {
  return request('/api/skill/open', { method: 'POST', body: JSON.stringify(payload) })
}
export function openProjectChat(payload) {
  return request('/api/project/open-chat', { method: 'POST', body: JSON.stringify(payload) })
}
export function getProjectSessions() {
  return request('/api/project/sessions')
}
export function getSkillFavorites() {
  return request('/api/skill/favorites')
}
export function setSkillFavorite(payload) {
  return request('/api/skill/favorite', { method: 'POST', body: JSON.stringify(payload) })
}
export function getCronJobs() {
  return request('/api/system/cron')
}
export function toggleCronJob(payload) {
  return request('/api/system/cron/toggle', { method: 'POST', body: JSON.stringify(payload) })
}
export function runCronJob(payload) {
  return request('/api/system/cron/run', { method: 'POST', body: JSON.stringify(payload) })
}
export function getActivity() {
  return request('/api/activity')
}
export function getSystemEnv() {
  return request('/api/system/env')
}
export function getWikiStats() {
  return request('/api/wiki/stats')
}
export function searchWiki(q) {
  return request(`/api/wiki/search?q=${encodeURIComponent(q)}`)
}
export function runAnalyze() {
  return request('/api/analyze/run', { method: 'POST' })
}
export function getAnalyzeLatest() {
  return request('/api/analyze/latest')
}
export function getAnalyzeHistory() {
  return request('/api/analyze/history')
}