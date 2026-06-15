<template>
  <div v-if="sources.length" class="card">
    <h2>📚 来源 ({{ sources.length }})</h2>
    <table class="sources-table">
      <thead>
        <tr>
          <th>#</th>
          <th>标题</th>
          <th>类型</th>
          <th>评分</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(s, i) in sources" :key="s.id || i">
          <td>{{ i + 1 }}</td>
          <td><a :href="s.url" target="_blank">{{ s.title }}</a></td>
          <td><span class="badge">{{ s.source_type || 'unknown' }}</span></td>
          <td>
            <div class="score-bar">
              <div class="score-fill" :style="{ width: ((s.score || 0) * 100) + '%' }"></div>
              <span>{{ ((s.score || 0) * 100).toFixed(0) }}</span>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
defineProps({ sources: { type: Array, default: () => [] } })
</script>

<style scoped>
.sources-table { width: 100%; border-collapse: collapse; }
.sources-table th, .sources-table td { padding: 8px 10px; text-align: left; border-bottom: 1px solid #eee; font-size: 0.9rem; }
.sources-table a { color: #1a73e8; word-break: break-all; }
.score-bar { display: flex; align-items: center; gap: 6px; min-width: 80px; }
.score-fill { height: 6px; background: #28a745; border-radius: 3px; }
</style>
