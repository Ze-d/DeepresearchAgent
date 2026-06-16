<template>
  <div v-if="reviewData" class="card review-panel">
    <h2>🛑 人工审核</h2>

    <div class="review-summary">
      <div class="stat">
        <span class="stat-value">{{ mergeSummary.total_sources }}</span>
        <span class="stat-label">来源</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ mergeSummary.total_evidences }}</span>
        <span class="stat-label">证据</span>
      </div>
      <div class="stat">
        <span class="stat-value">{{ mergeSummary.cross_validated_count }}</span>
        <span class="stat-label">交叉验证</span>
      </div>
      <div class="stat" v-if="mergeSummary.conflicts?.length">
        <span class="stat-value warning">{{ mergeSummary.conflicts.length }}</span>
        <span class="stat-label">冲突</span>
      </div>
    </div>

    <!-- Conflicts -->
    <div v-if="mergeSummary.conflicts?.length" class="conflicts-section">
      <h3>⚠️ 发现冲突</h3>
      <div v-for="(c, i) in mergeSummary.conflicts" :key="i" class="conflict-item">
        <p><strong>{{ c.topic }}</strong></p>
        <ul>
          <li v-for="(pos, agent) in c.positions" :key="agent">
            <span class="badge">{{ agent }}</span> {{ pos }}
          </li>
        </ul>
        <span class="severity" :class="c.severity">{{ c.severity }}</span>
      </div>
    </div>

    <!-- Bias warnings -->
    <div v-if="mergeSummary.source_bias_warnings?.length" class="warnings">
      <p v-for="w in mergeSummary.source_bias_warnings" :key="w" class="warning-text">
        ⚠️ {{ w }}
      </p>
    </div>

    <!-- Decision buttons -->
    <div class="review-actions">
      <button class="btn btn-primary" @click="decide('approve')" :disabled="submitting">
        ✅ 批准
      </button>
      <button class="btn btn-warning" @click="showAmend = !showAmend" :disabled="submitting">
        📝 补充搜索
      </button>
      <button class="btn btn-danger" @click="decide('redo')" :disabled="submitting">
        🔄 重做
      </button>
    </div>

    <!-- Amend input -->
    <div v-if="showAmend" class="amend-form">
      <textarea v-model="amendQueries" placeholder="输入补充搜索查询，一行一个..."></textarea>
      <textarea v-model="amendNotes" placeholder="补充说明（可选）..."></textarea>
      <button class="btn btn-primary" @click="decide('amend')" :disabled="submitting || !amendQueries.trim()">
        提交补充
      </button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  reviewData: { type: Object, default: null },
  taskId: { type: String, required: true },
})

const emit = defineEmits(['decision'])

const showAmend = ref(false)
const amendQueries = ref('')
const amendNotes = ref('')
const submitting = ref(false)
const error = ref('')

const mergeSummary = computed(() => props.reviewData?.merge_summary || {})

async function decide(action) {
  submitting.value = true
  error.value = ''
  try {
    const body = { action, notes: amendNotes.value }
    if (action === 'amend') {
      body.new_queries = amendQueries.value.split('\n').map(q => q.trim()).filter(Boolean)
    }
    const resp = await fetch(`/api/tasks/${props.taskId}/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!resp.ok) throw new Error(`Review submission failed: ${resp.status}`)
    emit('decision', body)
  } catch (e) {
    error.value = `提交失败: ${e.message}`
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.review-panel { border-left: 4px solid #f44747; }
.review-summary { display: flex; gap: 20px; margin-bottom: 16px; }
.stat { text-align: center; }
.stat-value { font-size: 1.5rem; font-weight: 700; color: #1a73e8; }
.stat-value.warning { color: #dc3545; }
.stat-label { font-size: 0.8rem; color: #666; }
.conflicts-section { background: #fff3cd; padding: 12px; border-radius: 6px; margin-bottom: 12px; }
.conflict-item { margin-bottom: 8px; }
.severity { font-size: 0.8rem; padding: 2px 8px; border-radius: 12px; }
.severity.major { background: #f8d7da; color: #721c24; }
.severity.minor { background: #fff3cd; color: #856404; }
.warnings { margin-bottom: 12px; }
.warning-text { color: #856404; font-size: 0.9rem; }
.review-actions { display: flex; gap: 12px; margin-top: 16px; }
.btn-warning { background: #ffc107; color: #333; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 0.95rem; font-weight: 500; }
.amend-form { margin-top: 12px; }
.amend-form textarea { width: 100%; margin-bottom: 8px; min-height: 60px; padding: 8px; border: 1px solid #ccc; border-radius: 6px; }
.error { color: #dc3545; margin-top: 8px; }
</style>
