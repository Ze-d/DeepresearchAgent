<template>
  <div v-if="plan" class="card">
    <h2>📋 研究计划</h2>
    <p><strong>目标:</strong> {{ plan.research_goal }}</p>
    <h3>子问题</h3>
    <ul>
      <li v-for="sq in plan.sub_questions" :key="sq.id">
        <span class="priority">P{{ sq.priority }}</span>
        {{ sq.question }}
        <div v-if="sq.search_queries?.length" class="search-queries">
          🔍 {{ sq.search_queries.join(' | ') }}
        </div>
      </li>
    </ul>
    <p v-if="plan.expected_sections?.length">
      <strong>预期章节:</strong> {{ plan.expected_sections.join(' → ') }}
    </p>
  </div>
</template>

<script setup>
defineProps({ plan: { type: Object, default: null } })
</script>

<style scoped>
.priority {
  display: inline-block; width: 24px; height: 24px;
  line-height: 24px; text-align: center;
  background: #1a73e8; color: #fff; border-radius: 50%;
  font-size: 0.75rem; margin-right: 6px;
}
.search-queries { font-size: 0.85rem; color: #888; margin: 2px 0 0 30px; }
</style>
