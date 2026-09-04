<script setup>
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { runSkill } from '@/api'

const props = defineProps({
  skill: { type: Object, default: null },
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const input = ref('')
const running = ref(false)
const messages = ref([])   // [{role: user|bot, text}]
const sessionId = ref('')  // 当前会话的 session_id
const isClaude = ref(false)

// 打开弹窗/换 skill 时重置会话
watch(() => [props.visible, props.skill], () => {
  if (props.visible && props.skill) {
    messages.value = []
    sessionId.value = ''
    input.value = ''
    isClaude.value = props.skill.source !== 'hermes'
  }
}, { immediate: true })

function close() {
  emit('update:visible', false)
}

async function send() {
  const q = input.value.trim()
  if (!q || running.value) {
    if (!q)
      message.warning('请输入问题')
    return
  }
  messages.value.push({ role: 'user', text: q })
  input.value = ''
  running.value = true
  try {
    const r = await runSkill({ slug: props.skill.slug, query: q, session_id: sessionId.value || undefined })
    sessionId.value = r.session_id || sessionId.value
    if (r.ok)
      messages.value.push({ role: 'bot', text: r.output })
    else
      messages.value.push({ role: 'bot', text: `❌ ${r.error || '执行失败'}` })
  }
  catch (e) {
    messages.value.push({ role: 'bot', text: `❌ ${e?.message || e}` })
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
        <a-tag :color="isClaude ? 'purple' : 'blue'">{{ isClaude ? 'Claude skill' : 'Hermes skill' }}</a-tag>
        <span v-if="skill.version">v{{ skill.version }}</span>
        <span style="margin-left:12px">{{ skill.description }}</span>
      </div>

      <!-- 消息列表 -->
      <div style="background:#0d1117;color:#e6edf3;border-radius:8px;padding:16px;min-height:200px;max-height:420px;overflow:auto;margin-bottom:12px;display:flex;flex-direction:column;gap:12px">
        <div v-if="!messages.length" style="color:#8b949e;text-align:center;font-size:12px;padding:40px 0">
          输入下面的问题开始对话。多轮对话会自动保持上下文。
        </div>
        <div
          v-for="(m, i) in messages"
          :key="i"
          :style="{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '90%',
            background: m.role === 'user' ? '#1f6feb' : '#161b22',
            borderRadius: '10px',
            padding: '8px 12px',
            fontSize: '13px',
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }"
        >
          {{ m.text }}
        </div>
        <div v-if="running" style="color:#58a6ff;font-size:12px">⏳ Hermes 正在执行 skill…</div>
      </div>

      <!-- 输入区 -->
      <div style="display:flex;gap:8px">
        <a-input
          v-model:value="input"
          placeholder="继续输入…（支持多轮对话，上下文自动保持）"
          :disabled="running"
          @keyup.enter="send"
        />
        <a-button type="primary" :loading="running" @click="send">
          发送
        </a-button>
      </div>
    </template>
  </a-modal>
</template>