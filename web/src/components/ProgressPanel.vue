<template>
  <div class="card">
    <h2>📊 执行进度</h2>
    <div class="progress-steps">
      <div
        v-for="node in nodes"
        :key="node.key"
        class="step"
        :class="stepClass(node.key)"
      >
        <span class="step-icon">{{ stepIcon(node.key) }}</span>
        <span class="step-label">{{ node.label }}</span>
      </div>
    </div>
    <p v-if="currentNode" class="current-step">
      当前: {{ nodeLabel(currentNode) }}
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  completedNodes: { type: Array, default: () => [] },
  currentNode: { type: String, default: null },
})

const nodes = [
  { key: 'plan', label: 'Plan' },
  { key: 'research', label: 'Research' },
  { key: 'summary', label: 'Summary' },
  { key: 'critique', label: 'Critique' },
  { key: 'final', label: 'Final' },
]

function stepClass(key) {
  if (props.completedNodes.includes(key)) return 'completed'
  if (props.currentNode === key) return 'active'
  return ''
}

function stepIcon(key) {
  if (props.completedNodes.includes(key)) return '✅'
  if (props.currentNode === key) return '⏳'
  return '⬜'
}

function nodeLabel(key) {
  const node = nodes.find(n => n.key === key)
  return node ? node.label : key
}
</script>

<style scoped>
.progress-steps { display: flex; gap: 8px; flex-wrap: wrap; }
.step {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 14px; border-radius: 20px; background: #f0f0f0;
  font-size: 0.9rem;
}
.step.completed { background: #d4edda; color: #155724; }
.step.active { background: #cce5ff; color: #004085; }
.step-icon { font-size: 1rem; }
.current-step { margin-top: 12px; color: #666; font-size: 0.9rem; }
</style>
