<script setup>
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getWikiStats, searchWiki } from '@/api'

const stats = ref(null)
const q = ref('')
const searching = ref(false)
const result = ref('')
const results = ref([])
const searched = ref(false)

async function loadStats() {
  try {
    stats.value = await getWikiStats()
  }
  catch { /* 统计失败不阻塞 */ }
}

async function doSearch() {
  const query = q.value.trim()
  if (!query) {
    message.warning('请输入搜索词')
    return
  }
  searching.value = true
  searched.value = true
  result.value = ''
  results.value = []
  try {
    const d = await searchWiki(query)
    if (d.ok) {
      try {
        const parsed = JSON.parse(d.output)
        if (parsed.results?.length)
          results.value = parsed.results
        else
          result.value = '（无结果）'
      }
      catch {
        result.value = d.output
      }
    }
    else {
      result.value = `❌ ${d.error || '搜索失败'}`
    }
  }
  catch (e) {
    result.value = `❌ ${e?.message || e}`
  }
  finally {
    searching.value = false
  }
}

onMounted(loadStats)
</script>

<template>
  <div class="wiki-page">
    <!-- Header -->
    <div class="wiki-header">
      <h2 class="wb-page-title">📚 知识库</h2>
      <span class="wiki-subtitle">llm-wiki · 本地笔记图谱</span>
    </div>

    <!-- Stats Cards -->
    <div v-if="stats" class="wb-stat-grid">
      <div class="wb-stat-card stat-entities">
        <div class="wb-stat-icon">🧩</div>
        <div>
          <div class="wb-stat-value">{{ stats.entities }}</div>
          <div class="wb-stat-label">实体 entities</div>
        </div>
      </div>
      <div class="wb-stat-card stat-topics">
        <div class="wb-stat-icon">🏷️</div>
        <div>
          <div class="wb-stat-value">{{ stats.topics }}</div>
          <div class="wb-stat-label">主题 topics</div>
        </div>
      </div>
      <div class="wb-stat-card stat-sources">
        <div class="wb-stat-icon">📄</div>
        <div>
          <div class="wb-stat-value">{{ stats.sources }}</div>
          <div class="wb-stat-label">素材 sources</div>
        </div>
      </div>
      <div class="wb-stat-card stat-synthesis">
        <div class="wb-stat-icon">✨</div>
        <div>
          <div class="wb-stat-value">{{ stats.synthesis }}</div>
          <div class="wb-stat-label">综述 synthesis</div>
        </div>
      </div>
    </div>

    <!-- Search Hero -->
    <div class="wiki-search-hero">
      <div class="wiki-search-row">
        <a-input
          v-model:value="q"
          placeholder="搜索知识库… 如: AI工具 / 交易策略 / 马一龙"
          size="large"
          class="wiki-search-input"
          @press-enter="doSearch"
        >
          <template #prefix>
            <span class="wiki-search-icon">🔍</span>
          </template>
        </a-input>
        <a-button
          type="primary"
          size="large"
          :loading="searching"
          class="wiki-search-btn"
          @click="doSearch"
        >
          搜索
        </a-button>
      </div>
      <div v-if="stats?.root" class="wiki-root-info">
        📁 {{ stats.root }}
      </div>
    </div>

    <!-- Search Results -->
    <div v-if="searched" class="wiki-results">
      <div class="wiki-results-header">
        <span class="wiki-results-title">搜索结果</span>
        <span class="wiki-results-query">「{{ q }}」</span>
        <a-tag v-if="results.length" class="wiki-results-count">
          {{ results.length }} 条
        </a-tag>
      </div>

      <!-- Loading -->
      <div v-if="searching" class="wiki-loading">
        <a-spin />
      </div>

      <!-- Structured Results -->
      <div v-else-if="results.length" class="wiki-result-list">
        <div
          v-for="(r, i) in results"
          :key="i"
          class="wiki-result-item"
        >
          <div class="wiki-result-head">
            <span class="wiki-result-title">{{ r.title }}</span>
            <span
              class="type-badge"
              :class="r.type === 'entity' ? 'type-entity' : r.type === 'topic' ? 'type-topic' : 'type-default'"
            >
              {{ r.type }}
            </span>
            <span v-if="r.match_type === 'graph'" class="wiki-match-type">图谱扩展</span>
          </div>

          <div class="wiki-result-score">
            <span class="score-label">相关度</span>
            <div class="score-bar">
              <div
                class="score-fill"
                :style="{ width: (r.score <= 1 ? r.score * 100 : Math.min(r.score, 100)) + '%' }"
              ></div>
            </div>
            <span class="score-value">{{ r.score }}</span>
          </div>

          <code class="wiki-result-path">{{ r.path }}</code>
          <p class="wiki-result-snippet">{{ r.snippet }}</p>
        </div>
      </div>

      <!-- Plain Text Result -->
      <pre v-else class="wiki-plain-result">{{ result }}</pre>
    </div>
  </div>
</template>

<style scoped>
.wiki-page {
  /* Local color extensions for stat types not covered by global tokens */
  --wb-success-bg: rgba(39, 166, 68, 0.1);
  --wb-warning-bg: rgba(245, 166, 35, 0.1);
  --wb-pink: #d6399c;
  --wb-pink-bg: rgba(214, 57, 156, 0.1);

  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ═══ Page Title ═══ */
.wb-page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
  color: var(--wb-text-primary);
  line-height: 1.3;
}

/* ═══ Header ═══ */
.wiki-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.wiki-subtitle {
  font-size: 12px;
  color: var(--wb-text-tertiary);
}

/* ═══ Stat Grid ═══
   Uses global .wb-stat-card / .wb-stat-icon / .wb-stat-value / .wb-stat-label
   Each variant sets its own icon-bg + value color via design tokens */
.wb-stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}
.stat-entities .wb-stat-icon { background: var(--wb-accent-bg); }
.stat-entities .wb-stat-value { color: var(--wb-accent); }
.stat-topics .wb-stat-icon { background: var(--wb-success-bg); }
.stat-topics .wb-stat-value { color: var(--wb-success); }
.stat-sources .wb-stat-icon { background: var(--wb-warning-bg); }
.stat-sources .wb-stat-value { color: var(--wb-warning); }
.stat-synthesis .wb-stat-icon { background: var(--wb-pink-bg); }
.stat-synthesis .wb-stat-value { color: var(--wb-pink); }

/* ═══ Search Hero ═══ */
.wiki-search-hero {
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-lg);
  padding: 24px;
  box-shadow: var(--wb-shadow-sm);
}
.wiki-search-row {
  display: flex;
  gap: 12px;
  align-items: stretch;
}
.wiki-search-input {
  flex: 1;
}
.wiki-search-input :deep(.ant-input-affix-wrapper) {
  border-radius: var(--wb-radius-md) !important;
  padding: 8px 16px;
  font-size: 15px;
  border-color: var(--wb-border-light);
  transition: all var(--wb-transition);
  height: 44px;
}
.wiki-search-input :deep(.ant-input-affix-wrapper:hover) {
  border-color: var(--wb-border-focus) !important;
}
.wiki-search-input :deep(.ant-input-affix-wrapper-focused) {
  border-color: var(--wb-border-focus) !important;
  box-shadow: var(--wb-shadow-glow) !important;
}
.wiki-search-icon {
  font-size: 16px;
  opacity: 0.5;
}
.wiki-search-btn {
  border-radius: var(--wb-radius-md) !important;
  font-weight: 600;
  padding: 0 28px;
  height: 44px;
}
.wiki-root-info {
  font-size: 12px;
  color: var(--wb-text-tertiary);
  margin-top: 12px;
  font-family: var(--wb-font-mono);
}

/* ═══ Results ═══ */
.wiki-results {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.wiki-results-header {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wiki-results-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--wb-text-primary);
}
.wiki-results-query {
  font-size: 13px;
  color: var(--wb-text-secondary);
}
.wiki-results-count {
  margin-left: 4px;
  border-radius: 6px;
  font-size: 12px;
}

/* Loading */
.wiki-loading {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 48px 0;
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-md);
}

/* Result List */
.wiki-result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.wiki-result-item {
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-md);
  padding: 16px 20px;
  transition: all var(--wb-transition);
}
.wiki-result-item:hover {
  border-color: var(--wb-border-light);
  box-shadow: var(--wb-shadow-md);
  transform: translateY(-1px);
}

.wiki-result-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.wiki-result-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--wb-text-primary);
}

/* Type Badges */
.type-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.2px;
  line-height: 1.5;
}
.type-entity {
  background: var(--wb-accent-bg);
  color: var(--wb-accent);
}
.type-topic {
  background: var(--wb-success-bg);
  color: var(--wb-success);
}
.type-default {
  background: rgba(0, 0, 0, 0.04);
  color: var(--wb-text-tertiary);
}
.wiki-match-type {
  font-size: 11px;
  color: var(--wb-text-tertiary);
}

/* Score Progress Bar */
.wiki-result-score {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.score-label {
  font-size: 11px;
  color: var(--wb-text-tertiary);
  white-space: nowrap;
}
.score-bar {
  flex: 1;
  max-width: 120px;
  height: 4px;
  background: var(--wb-border-light);
  border-radius: 2px;
  overflow: hidden;
}
.score-fill {
  height: 100%;
  background: var(--wb-accent);
  border-radius: 2px;
  transition: width var(--wb-transition-slow);
}
.score-value {
  font-size: 11px;
  font-weight: 600;
  color: var(--wb-accent);
  font-family: var(--wb-font-mono);
}

/* Path (mono) */
.wiki-result-path {
  display: block;
  font-family: var(--wb-font-mono);
  font-size: 11px;
  color: var(--wb-text-tertiary);
  background: var(--wb-bg);
  padding: 4px 8px;
  border-radius: var(--wb-radius-sm);
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Snippet */
.wiki-result-snippet {
  font-size: 13px;
  color: var(--wb-text-secondary);
  line-height: 1.7;
  margin: 0;
}

/* Plain Text Result */
.wiki-plain-result {
  max-height: 520px;
  overflow: auto;
  background: var(--wb-bg);
  padding: 16px;
  border-radius: var(--wb-radius-md);
  border: 1px solid var(--wb-border);
  font-size: 13px;
  font-family: var(--wb-font-mono);
  color: var(--wb-text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
  line-height: 1.6;
}
</style>
