<script setup>
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { openSkill } from '@/api'

const props = defineProps({
  skill: { type: Object, default: null },
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['update:visible'])

const opening = ref(false)

function close() {
  emit('update:visible', false)
}

async function launch() {
  opening.value = true
  try {
    const r = await openSkill({ slug: props.skill.slug })
    if (r.ok)
      message.success(r.msg || '已在 Terminal 打开对话')
    else
      message.error(r.error || '启动失败')
    close()
  }
  catch (e) {
    message.error(e?.message || '启动失败')
  }
  finally {
    opening.value = false
  }
}
</script>

<template>
  <a-modal
    :visible="visible"
    :title="skill ? `${skill.source === 'hermes' ? '🤖' : '📚'} ${skill.name}` : ''"
    :footer="null"
    width="560px"
    @cancel="close"
  >
    <template v-if="skill">
      <div style="display:flex;align-items:flex-start;gap:12px">
        <div
          style="width:46px;height:46px;border-radius:10px;flex:none;display:flex;align-items:center;justify-content:center;font-size:22px;color:#fff;background:linear-gradient(135deg,#1f6feb,#8957e5)"
        >
          {{ skill.source === 'hermes' ? '🤖' : '📚' }}
        </div>
        <div style="flex:1">
          <div style="display:flex;align-items:center;gap:8px">
            <b style="font-size:15px">{{ skill.name }}</b>
            <a-tag :color="skill.source === 'hermes' ? 'blue' : 'purple'" style="font-size:11px">
              {{ skill.source === 'hermes' ? 'Hermes skill' : 'Claude skill' }}
            </a-tag>
          </div>
          <p style="font-size:13px;color:#666;margin:8px 0 0;line-height:1.5">{{ skill.description }}</p>
        </div>
      </div>

      <div style="background:#f6f8fa;border-radius:8px;padding:12px 14px;margin:16px 0;font-size:13px">
        <div style="font-weight:600;margin-bottom:6px">在原生 Terminal 中打开对话</div>
        <div style="color:#57606a;line-height:1.6">
          将打开一个 Hermes 交互式对话（<code style="background:#eaeef2;padding:1px 5px;border-radius:4px;font-size:12px">hermes chat --skills {{ skill.slug }}</code>）。
          <br>
          多轮对话、记忆、流式输出、工具调用全部由 Hermes 原生完成。
        </div>
      </div>

      <div style="display:flex;justify-content:flex-end;gap:8px">
        <a-button @click="close">取消</a-button>
        <a-button type="primary" :loading="opening" @click="launch">
          打开对话
        </a-button>
      </div>
    </template>
  </a-modal>
</template>