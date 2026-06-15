<template>
  <div v-if="critique" class="card">
    <h2>🔍 Critique 评分</h2>
    <div class="critique-overview">
      <div class="overall-score">
        <span class="score-number">{{ ((critique.overall_score || 0) * 100).toFixed(0) }}</span>
        <span class="score-label">总分</span>
      </div>
      <span class="badge" :class="critique.pass ? 'badge-completed' : 'badge-failed'">
        {{ critique.pass ? '✅ 通过' : '❌ 未通过' }}
      </span>
    </div>

    <div v-if="critique.dimensions" class="dimensions">
      <div class="dimension" v-for="(dim, key) in critique.dimensions" :key="key">
        <div class="dim-header">
          <span class="dim-name">{{ dimLabel(key) }}</span>
          <span class="dim-score" :class="dim.status">{{ ((dim.score || 0) * 100).toFixed(0) }}%</span>
        </div>
        <div class="dim-bar">
          <div class="dim-fill" :class="dim.status" :style="{ width: ((dim.score || 0) * 100) + '%' }"></div>
        </div>
        <p v-if="dim.issues?.length" class="dim-issues">{{ dim.issues.join('; ') }}</p>
      </div>
    </div>

    <div v-if="metrics?.length" class="fix-rate">
      Fix Rate: {{ lastFixRate }}% ({{ metrics[metrics.length - 1].issues_count }} issues)
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  critique: { type: Object, default: null },
  metrics: { type: Array, default: () => [] },
})

const lastFixRate = computed(() => {
  if (!props.metrics.length) return 'N/A'
  const last = props.metrics[props.metrics.length - 1]
  return last.fix_rate != null ? (last.fix_rate * 100).toFixed(0) : 'N/A'
})

function dimLabel(key) {
  const map = { fact_check: '事实核查', logic_coherence: '逻辑一致性', coverage: '覆盖度' }
  return map[key] || key
}
</script>

<style scoped>
.critique-overview { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; }
.overall-score { display: flex; flex-direction: column; align-items: center; }
.score-number { font-size: 2rem; font-weight: 700; color: #1a73e8; }
.score-label { font-size: 0.85rem; color: #666; }
.dimensions { display: flex; flex-direction: column; gap: 10px; }
.dimension { font-size: 0.9rem; }
.dim-header { display: flex; justify-content: space-between; margin-bottom: 4px; }
.dim-score.pass { color: #28a745; font-weight: 600; }
.dim-score.fail { color: #dc3545; font-weight: 600; }
.dim-bar { height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; }
.dim-fill.pass { background: #28a745; }
.dim-fill.fail { background: #dc3545; }
.dim-issues { font-size: 0.8rem; color: #dc3545; margin: 4px 0 0; }
.fix-rate { margin-top: 12px; font-size: 0.9rem; color: #555; }
</style>
