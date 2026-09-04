<script setup>
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { getSkills, getSkillFavorites, setSkillFavorite } from '@/api'
import SkillDialog from '@/components/SkillDialog.vue'

const skills = ref([])
const skillsLoading = ref(false)
const skillFilter = ref('')
const sourceFilter = ref('all')
const skillDialog = ref({ visible: false, skill: null })
const favs = ref([])
const favLoading = ref(false)

function favKey(s) {
  return `${s.slug}__${s.source}`
}
function isFav(s) {
  return favs.value.includes(favKey(s))
}

async function loadFavs() {
  try {
    const d = await getSkillFavorites()
    favs.value = d.favorites || []
  }
  catch { /* 收藏加载失败不阻塞 */ }
}

async function toggleFav(s, e) {
  e.stopPropagation()
  const key = favKey(s)
  const willFav = !isFav(s)
  favLoading.value = true
  try {
    const d = await setSkillFavorite({ key, favorite: willFav })
    favs.value = d.favorites || []
    message.success(willFav ? `已收藏 ${s.name}` : `已取消收藏 ${s.name}`)
  }
  catch (err) {
    message.error('收藏操作失败: ' + (err?.message || err))
  }
  finally {
    favLoading.value = false
  }
}

async function loadSkills() {
  skillsLoading.value = true
  try {
    const d = await getSkills()
    skills.value = d.skills || []
  }
  catch (e) {
    message.error('加载技能失败: ' + (e?.message || e))
  }
  finally {
    skillsLoading.value = false
  }
}

const countBySource = computed(() => {
  const c = { hermes: 0, claude: 0 }
  skills.value.forEach(s => { c[s.source] = (c[s.source] || 0) + 1 })
  return c
})

const favCount = computed(() => skills.value.filter(s => isFav(s)).length)

// 收藏的置顶, 其余保持原顺序
const filteredSkills = computed(() => {
  const q = skillFilter.value.trim().toLowerCase()
  let list = skills.value
  if (sourceFilter.value !== 'all')
    list = list.filter(s => s.source === sourceFilter.value)
  if (q) {
    list = list.filter(s =>
      s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q) || s.slug.toLowerCase().includes(q))
  }
  return [...list].sort((a, b) => (isFav(b) ? 1 : 0) - (isFav(a) ? 1 : 0))
})

function openSkill(skill) {
  skillDialog.value = { visible: true, skill }
}

onMounted(() => {
  loadSkills()
  loadFavs()
})
</script>

<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <h2 style="margin:0;font-size:18px">🧪 Agent 能力墙</h2>
      <a-tag color="blue">{{ skillsLoading ? '…' : skills.length }}</a-tag>
      <a-tag v-if="favCount" color="gold">⭐ {{ favCount }} 收藏</a-tag>
      <span style="font-size:12px;color:#999">点卡片对话 · ⭐ 收藏常用能力置顶</span>
      <div style="flex:1"></div>
      <a-select v-model:value="sourceFilter" style="width:110px" size="small">
        <a-select-option value="all">全部来源</a-select-option>
        <a-select-option value="hermes">Hermes ({{ countBySource.hermes }})</a-select-option>
        <a-select-option value="claude">Claude ({{ countBySource.claude }})</a-select-option>
      </a-select>
      <a-input
        v-model:value="skillFilter"
        placeholder="搜索能力…"
        allow-clear
        style="width:220px"
      />
      <a-button size="small" @click="loadSkills">刷新</a-button>
    </div>

    <a-skeleton :loading="skillsLoading" active>
      <div
        v-if="filteredSkills.length"
        style="display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px"
      >
        <a-card
          v-for="s in filteredSkills"
          :key="favKey(s)"
          hoverable
          size="small"
          style="border-radius:8px;cursor:pointer"
          @click="openSkill(s)"
        >
          <div style="display:flex;justify-content:space-between;align-items:center">
            <b style="font-size:13px">{{ s.name }}</b>
            <span style="display:flex;align-items:center;gap:6px">
              <a-tag :color="s.source === 'hermes' ? 'blue' : 'purple'" style="font-size:11px;margin:0">
                {{ s.source === 'hermes' ? 'H' : 'C' }}
              </a-tag>
              <span
                :class="{ 'fav-star': true, active: isFav(s) }"
                :title="isFav(s) ? '取消收藏' : '收藏置顶'"
                @click="toggleFav(s, $event)"
                style="font-size:15px;cursor:pointer;user-select:none"
              >⭐</span>
            </span>
          </div>
          <p style="font-size:12px;color:#888;margin:6px 0 0;min-height:32px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">
            {{ s.description }}
          </p>
        </a-card>
      </div>
      <a-empty v-else-if="!skillsLoading" description="暂无能力" />
    </a-skeleton>

    <SkillDialog v-model:visible="skillDialog.visible" :skill="skillDialog.skill" />
  </div>
</template>

<style scoped>
.fav-star {
  opacity: 0.35;
  filter: grayscale(1);
  transition: all 0.2s;
}
.fav-star.active {
  opacity: 1;
  filter: none;
}
.fav-star:hover {
  opacity: 1;
  filter: none;
  transform: scale(1.15);
}
</style>