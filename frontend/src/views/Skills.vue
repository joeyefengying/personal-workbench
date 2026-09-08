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
  <div class="wb-skills">
    <!-- Header Bar -->
    <div class="wb-skills-header">
      <div class="wb-skills-header-left">
        <h2 class="wb-page-title">Agent 能力墙</h2>
        <a-tag color="blue">{{ skillsLoading ? '…' : skills.length }}</a-tag>
        <a-tag v-if="favCount" color="gold">⭐ {{ favCount }} 收藏</a-tag>
        <span class="wb-page-hint">点卡片对话 · ⭐ 收藏常用能力置顶</span>
      </div>
      <div class="wb-skills-header-right">
        <a-select v-model:value="sourceFilter" style="width: 130px" size="small">
          <a-select-option value="all">全部来源</a-select-option>
          <a-select-option value="hermes">Hermes ({{ countBySource.hermes }})</a-select-option>
          <a-select-option value="claude">Claude ({{ countBySource.claude }})</a-select-option>
        </a-select>
        <a-input
          v-model:value="skillFilter"
          placeholder="搜索能力…"
          allow-clear
          style="width: 220px"
          size="small"
        />
        <a-button size="small" @click="loadSkills">刷新</a-button>
      </div>
    </div>

    <a-skeleton :loading="skillsLoading" active>
      <div v-if="filteredSkills.length" class="wb-skill-grid">
        <div
          v-for="s in filteredSkills"
          :key="favKey(s)"
          class="wb-skill-card"
          :class="{ 'wb-skill-card-fav': isFav(s) }"
          @click="openSkill(s)"
        >
          <!-- Source accent bar -->
          <div
            class="wb-skill-accent"
            :class="s.source === 'hermes' ? 'wb-skill-accent-h' : 'wb-skill-accent-c'"
          ></div>

          <div class="wb-skill-content">
            <div class="wb-skill-top">
              <span class="wb-skill-name">{{ s.name }}</span>
              <div class="wb-skill-badges">
                <span
                  class="wb-skill-source"
                  :class="s.source === 'hermes' ? 'wb-source-h' : 'wb-source-c'"
                >
                  {{ s.source === 'hermes' ? 'H' : 'C' }}
                </span>
                <span
                  class="wb-skill-star"
                  :class="{ active: isFav(s) }"
                  :title="isFav(s) ? '取消收藏' : '收藏置顶'"
                  @click="toggleFav(s, $event)"
                >⭐</span>
              </div>
            </div>
            <p class="wb-skill-desc">{{ s.description }}</p>
          </div>
        </div>
      </div>
      <a-empty v-else-if="!skillsLoading" description="暂无能力" style="padding: 60px 0" />
    </a-skeleton>

    <SkillDialog v-model:visible="skillDialog.visible" :skill="skillDialog.skill" />
  </div>
</template>

<style scoped>
.wb-skills {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wb-skills-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
}
.wb-skills-header-left,
.wb-skills-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wb-page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
}
.wb-page-hint {
  font-size: 12px;
  color: var(--wb-text-tertiary);
}

.wb-skill-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
}

.wb-skill-card {
  background: var(--wb-bg-elevated);
  border: 1px solid var(--wb-border);
  border-radius: var(--wb-radius-md);
  cursor: pointer;
  overflow: hidden;
  transition: all var(--wb-transition);
  position: relative;
}
.wb-skill-card:hover {
  box-shadow: var(--wb-shadow-md);
  border-color: var(--wb-border-light);
  transform: translateY(-1px);
}
.wb-skill-card-fav {
  border-color: rgba(245, 166, 35, 0.3);
  box-shadow: 0 0 0 1px rgba(245, 166, 35, 0.12);
}

.wb-skill-accent {
  height: 3px;
  width: 100%;
}
.wb-skill-accent-h {
  background: linear-gradient(90deg, #5e6ad2, #7170ff);
}
.wb-skill-accent-c {
  background: linear-gradient(90deg, #7c3aed, #a855f7);
}

.wb-skill-content {
  padding: 14px 16px;
}
.wb-skill-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.wb-skill-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--wb-text-primary);
}
.wb-skill-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}
.wb-skill-source {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--wb-font-mono);
}
.wb-source-h {
  background: rgba(94, 106, 210, 0.12);
  color: #5e6ad2;
}
.wb-source-c {
  background: rgba(124, 58, 237, 0.12);
  color: #7c3aed;
}

.wb-skill-star {
  font-size: 14px;
  cursor: pointer;
  user-select: none;
  opacity: 0.3;
  filter: grayscale(1);
  transition: all var(--wb-transition);
}
.wb-skill-star.active {
  opacity: 1;
  filter: none;
}
.wb-skill-star:hover {
  opacity: 1;
  filter: none;
  transform: scale(1.2);
}

.wb-skill-desc {
  font-size: 12px;
  color: var(--wb-text-tertiary);
  margin: 4px 0 0;
  min-height: 32px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  line-height: 1.5;
}
</style>
