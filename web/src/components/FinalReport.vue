<template>
  <div class="card">
    <h2>📄 最终报告</h2>
    <div class="markdown-body" v-html="rendered"></div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps({ report: { type: String, required: true } })

const rendered = computed(() => {
  return marked.parse(props.report) || ''
})
</script>
