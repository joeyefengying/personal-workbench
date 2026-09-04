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
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <h2 style="margin:0;font-size:18px">📚 知识库</h2>
      <span style="font-size:12px;color:#999">llm-wiki · 本地笔记图谱</span>
      <div style="flex:1"></div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px">
      <a-card size="small" style="border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#1677ff">{{ stats.entities }}</div>
        <div style="font-size:12px;color:#999">实体 entities</div>
      </a-card>
      <a-card size="small" style="border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#52c41a">{{ stats.topics }}</div>
        <div style="font-size:12px;color:#999">主题 topics</div>
      </a-card>
      <a-card size="small" style="border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#faad14">{{ stats.sources }}</div>
        <div style="font-size:12px;color:#999">素材 sources</div>
      </a-card>
      <a-card size="small" style="border-radius:8px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#eb2f96">{{ stats.synthesis }}</div>
        <div style="font-size:12px;color:#999">综述 synthesis</div>
      </a-card>
    </div>

    <!-- 搜索 -->
    <a-card size="small" style="border-radius:8px;margin-bottom:16px">
      <div style="display:flex;gap:10px">
        <a-input
          v-model:value="q"
          placeholder="搜索知识库… 如: AI工具 / 交易策略 / 马一龙"
          size="large"
          @press-enter="doSearch"
        />
        <a-button type="primary" size="large" :loading="searching" @click="doSearch">
          搜索
        </a-button>
      </div>
      <div v-if="stats?.root" style="font-size:12px;color:#bbb;margin-top:8px">
        📁 {{ stats.root }}
      </div>
    </a-card>

    <!-- 搜索结果 -->
    <a-card v-if="searched" size="small" style="border-radius:8px">
      <template #title>搜索结果 · {{ q }} <a-tag v-if="results.length" color="blue" style="margin-left:6px">{{ results.length }} 条</a-tag></template>

      <!-- 结构化结果卡片 -->
      <a-spin v-if="searching" style="display:block;padding:40px 0" />
      <template v-else-if="results.length">
        <div v-for="(r, i) in results" :key="i" style="padding:10px 0;border-bottom:1px solid #f0f0f0">
          <div style="display:flex;align-items:center;gap:8px">
            <b style="font-size:14px">{{ r.title }}</b>
            <a-tag :color="r.type === 'entity' ? 'blue' : r.type === 'topic' ? 'green' : 'default'" style="font-size:11px">
              {{ r.type }}
            </a-tag>
            <span v-if="r.match_type === 'graph'" style="font-size:11px;color:#999">图谱扩展</span>
          </div>
          <a-tag color="gold" style="font-size:11px;margin-top:4px">相关度 {{ r.score }}</a-tag>
          <code style="display:block;font-size:11px;color:#888;margin-top:2px">{{ r.path }}</code>
          <p style="font-size:13px;color:#555;margin:6px 0 0;line-height:1.6">{{ r.snippet }}</p>
        </div>
      </template>
      <template v-else>
        <pre style="max-height:520px;overflow:auto;background:#fafafa;padding:12px;border-radius:8px;font-size:13px;white-space:pre-wrap;word-break:break-all;margin:0">{{ result }}</pre>
      </template>
    </a-card>
  </div>
</template>