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