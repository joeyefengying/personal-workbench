<script setup>
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { runSkill } from '@/api'

const props = defineProps({
  skill: { type: Object, default: null },
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const query = ref('')
const running = ref(false)
const output = ref('')
const done = ref(false)
const error = ref('')

const isHermes = () => props.skill?.source === 'hermes'

function close() {
  emit('update:visible', false)
  // 重置状态
  setTimeout(() => {
    query.value = ''
    output.value = ''
    done.value = false
    error.value = ''
  }, 300)
}

async function send() {
  if (!query.value.trim()) {
    message.warning('请输入问题')
    return
  }
  running.value = true
  done.value = false
  output.value = ''
  error.value = ''
  try {
    const r = await runSkill({ slug: props.skill.slug, query: query.value })
    if (r.ok) {
      output.value = r.output
      done.value = true
    }
    else {
      error.value = r.error || '执行失败'
    }
  }
  catch (e) {
    error.value = String(e?.message || e)
  }
  finally {
    running.value = false
  }
}
</script>

<template>
  <a-modal
    :visible="visible"
    :title="skill ? `${skill.source === 'hermes' ? '🤖' : '📚'} ${skill.name}  ·  能力对话` : ''"
    :footer="null"
    width="760px"
    @cancel="close"
  >
    <template v-if="skill">
      <div style="font-size:12px;color:#999;margin-bottom:12px">
        <a-tag :color="isHermes() ? 'blue' : 'purple'">{{ isHermes() ? 'Hermes skill' : 'Claude skill' }}</a-tag>
        <span v-if="skill.version">v{{ skill.version }}</span>
        <span style="margin-left:12px">{{ skill.description }}</span>
      </div>

      <!-- 输出区 -->
      <div v-if="running || done || error" style="background:#0d1117;color:#e6edf3;border-radius:8px;padding:16px;min-height:120px;max-height:360px;overflow:auto;font-family:monospace;font-size:13px;white-space:pre-wrap;margin-bottom:12px">
        <div v-if="running" style="color:#58a6ff">⏳ Hermes 正在执行 skill…</div>
        <div v-else-if="error" style="color:#f85149">{{ error }}</div>
        <div v-else>{{ output }}</div>
      </div>

      <!-- 输入区 -->
      <div style="display:flex;gap:8px">
        <a-input
          v-model:value="query"
          placeholder="输入问题，例如：帮我消化这篇 <url> / 筛选简历 <文件夹> / 问这个代码库…"
          :disabled="running"
          @keyup.enter="send"
        />
        <a-button type="primary" :loading="running" @click="send">
          发送
        </a-button>
      </div>
      <div v-if="!isHermes()" style="margin-top:8px;font-size:12px;color:#faad14">
        ⚠️ 该 skill 来自 Claude 体系（.claude/skills），Hermes 未注册。将用通用方式调用，部分流程可能不完整。
      </div>
    </template>
  </a-modal>
</template>