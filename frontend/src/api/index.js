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
// ---------- 轻推 (Qingtui) ----------
export function getQtStatus() {
  return request('/api/qingtui/status')
}
export function launchQt() {
  return request('/api/qingtui/launch', { method: 'POST' })
}
export function getQtSessions() {
  return request('/api/qingtui/sessions')
}
export function getQtWatch() {
  return request('/api/qingtui/watch')
}
export function setQtWatch(sessions) {
  return request('/api/qingtui/watch', { method: 'POST', body: JSON.stringify({ sessions }) })
}
export function getQtDailySummary(date, sessions) {
  const q = new URLSearchParams()
  if (date) q.set('date', date)
  if (sessions) q.set('sessions', sessions)
  return request(`/api/qingtui/daily-summary?${q}`)
}
export function getQtTasks(date, sessions) {
  const q = new URLSearchParams()
  if (date) q.set('date', date)
  if (sessions) q.set('sessions', sessions)
  return request(`/api/qingtui/tasks?${q}`)
}
export function getQtContext(chatId, ts, direction = '', cursorTs = 0) {
  const p = { chat_id: chatId }
  if (ts) p.ts = ts
  if (direction) p.direction = direction
  if (cursorTs) p.cursor_ts = cursorTs
  const qs = new URLSearchParams(p)
  return request(`/api/qingtui/context?${qs}`)
}
export function getQtContextPage(chatId, cursorTs, direction) {
  return getQtContext(chatId, 0, direction, cursorTs)
}

export function verifyQtTask(taskId, status) {
  return request('/api/qingtui/task/verify', { method: 'POST', body: JSON.stringify({ task_id: taskId, status }) })
}

export function getQtDocs(days = 7, date = '', type = '', chatId = '') {
  const q = new URLSearchParams()
  if (days) q.set('days', days)
  if (date) q.set('date', date)
  if (type) q.set('type', type)
  if (chatId) q.set('chat_id', chatId)
  return request(`/api/qingtui/docs?${q}`)
}

// ---------- 统一时间线 ----------
export function getTimelineEvents(p = {}) {
  const qs = new URLSearchParams()
  Object.entries(p).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, v) })
  return request(`/api/timeline/events?${qs}`)
}
export function getTimelineStats(date) {
  return request(`/api/timeline/stats${date ? '?date=' + encodeURIComponent(date) : ''}`)
}
export function getTimelineDates(limit = 60) {
  return request(`/api/timeline/dates?limit=${limit}`)
}
export function getTimelineDaily(date) {
  return request(`/api/timeline/daily${date ? '?date=' + encodeURIComponent(date) : ''}`)
}
export function triggerCollect() {
  return request('/api/timeline/collect', { method: 'POST' })
}
export function timelineCollectSync() {
  return request('/api/timeline/collect/sync', { method: 'POST' })
}
export function timelineObsidianProjects() {
  return request('/api/timeline/obsidian/projects', { method: 'POST' })
}
export function getTimelineChannels() {
  return request('/api/timeline/channels')
}
export function triggerLifecycle(ttlDays = 30) {
  return request(`/api/timeline/lifecycle?ttl_days=${ttlDays}`, { method: 'POST' })
}
export function getTimelineSummary(date = '', source = '') {
  const q = new URLSearchParams()
  if (date) q.set('date', date)
  if (source) q.set('source', source)
  return request(`/api/timeline/summary?${q}`)
}
export function previewDailyReport(date) {
  return request('/api/timeline/daily/preview', { method: 'POST', body: JSON.stringify({ date }) })
}
export function commitDailyReport(date, projectSummaries) {
  return request('/api/timeline/daily/commit', { method: 'POST', body: JSON.stringify({ date, project_summaries: projectSummaries }) })
}
export function getTodayOverview(date = '') {
  return request(`/api/timeline/today-overview${date ? '?date=' + encodeURIComponent(date) : ''}`)
}

// ---------- 周报/月报 ----------
export function listWeeklyReports() {
  return request('/api/weekly/list')
}
export function getWeeklyReport(week) {
  return request(`/api/weekly/report?week=${encodeURIComponent(week)}`)
}
export function exportWeeklyMarkdown(week) {
  return request(`/api/weekly/export-md?week=${encodeURIComponent(week)}`)
}
export function listMonthlyReports() {
  return request('/api/monthly/list')
}
export function getMonthlyReport(month) {
  return request(`/api/monthly/report?month=${encodeURIComponent(month)}`)
}
export function exportMonthlyMarkdown(month) {
  return request(`/api/monthly/export-md?month=${encodeURIComponent(month)}`)
}
export function summarizeWeekly(week, force = false) {
  return request(`/api/weekly/summarize?week=${encodeURIComponent(week)}${force ? '&force=true' : ''}`)
}
export function summarizeMonthly(month, force = false) {
  return request(`/api/monthly/summarize?month=${encodeURIComponent(month)}${force ? '&force=true' : ''}`)
}
export function writeWeeklyToLifeOS(week) {
  return request('/api/weekly/write-lifeos', { method: 'POST', body: JSON.stringify({ week }) })
}
export function writeMonthlyToLifeOS(month) {
  return request('/api/monthly/write-lifeos', { method: 'POST', body: JSON.stringify({ month }) })
}

// ---------- 季报/年报 ----------
export function listQuarterlyReports() {
  return request('/api/quarterly/list')
}
export function getQuarterlyReport(quarter) {
  return request(`/api/quarterly/report?quarter=${encodeURIComponent(quarter)}`)
}
export function summarizeQuarterly(quarter, force = false) {
  return request(`/api/quarterly/summarize?quarter=${encodeURIComponent(quarter)}${force ? '&force=true' : ''}`)
}
export function writeQuarterlyToLifeOS(quarter) {
  return request('/api/quarterly/write-lifeos', { method: 'POST', body: JSON.stringify({ quarter }) })
}
export function listYearlyReports() {
  return request('/api/yearly/list')
}
export function getYearlyReport(year) {
  return request(`/api/yearly/report?year=${encodeURIComponent(year)}`)
}
export function summarizeYearly(year, force = false) {
  return request(`/api/yearly/summarize?year=${encodeURIComponent(year)}${force ? '&force=true' : ''}`)
}
export function writeYearlyToLifeOS(year) {
  return request('/api/yearly/write-lifeos', { method: 'POST', body: JSON.stringify({ year }) })
}

// ---------- 工作周报 DOC ----------
export function listDocWeeks() {
  return request('/api/weekly/doc/weeks')
}
export function previewWeeklyDoc(week_start) {
  return request('/api/weekly/doc/preview', { method: 'POST', body: JSON.stringify({ week_start }) })
}
export function generateWeeklyDoc(week_start) {
  return request('/api/weekly/doc/generate', { method: 'POST', body: JSON.stringify({ week_start }) })
}

// ---------- 日报 ----------
export function listDailyDates() {
  return request('/api/daily/dates')
}
export function getDailyReport(date) {
  return request(`/api/daily/report?date=${encodeURIComponent(date)}`)
}
export function runDailyDigest() {
  return request('/api/daily-report/run', { method: 'POST' })
}
