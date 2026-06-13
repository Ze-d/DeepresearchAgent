<template>
  <div v-if="evidences.length" class="card">
    <h2>🔬 证据 ({{ evidences.length }})</h2>
    <div class="evidence-item" v-for="ev in evidences" :key="ev.id">
      <div class="evidence-claim">
        <span class="confidence" :class="confidenceClass(ev.confidence)">
          {{ ((ev.confidence || 0) * 100).toFixed(0) }}%
        </span>
        {{ ev.claim }}
      </div>
      <blockquote v-if="ev.quote">{{ ev.quote }}</blockquote>
    </div>
  </div>
</template>

<script setup>
defineProps({ evidences: { type: Array, default: () => [] } })

function confidenceClass(c) {
  if (c >= 0.8) return 'high'
  if (c >= 0.5) return 'medium'
  return 'low'
}
</script>

<style scoped>
.evidence-item { margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #f0f0f0; }
.evidence-claim { display: flex; align-items: flex-start; gap: 8px; }
.confidence {
  display: inline-block; padding: 2px 8px; border-radius: 12px;
  font-size: 0.8rem; font-weight: 600; white-space: nowrap;
}
.confidence.high { background: #d4edda; color: #155724; }
.confidence.medium { background: #fff3cd; color: #856404; }
.confidence.low { background: #f8d7da; color: #721c24; }
blockquote { border-left: 3px solid #ccc; padding-left: 12px; color: #666; font-size: 0.9rem; margin: 6px 0 0; }
</style>
