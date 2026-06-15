<template>
  <div class="card">
    <h2>📝 新建研究任务</h2>
    <form @submit.prevent="submit">
      <div class="form-row">
        <input
          v-model="query"
          type="text"
          placeholder="输入研究问题..."
          :disabled="submitting"
          required
        />
      </div>
      <div class="form-row form-options">
        <label>
          最大迭代
          <input v-model.number="maxIterations" type="number" min="1" max="5" />
        </label>
        <button type="submit" class="btn btn-primary" :disabled="submitting || !query.trim()">
          {{ submitting ? '⏳ 提交中...' : '🚀 开始研究' }}
        </button>
      </div>
    </form>
    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createTask } from '../api/index.js'

const router = useRouter()
const query = ref('')
const maxIterations = ref(2)
const submitting = ref(false)
const error = ref('')

async function submit() {
  if (!query.value.trim()) return
  submitting.value = true
  error.value = ''
  try {
    const task = await createTask(query.value.trim(), maxIterations.value)
    router.push(`/tasks/${task.task_id}`)
  } catch (e) {
    error.value = `提交失败: ${e.message}`
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.form-row { margin-bottom: 12px; }
.form-options { display: flex; align-items: center; gap: 16px; }
.form-options label { display: flex; align-items: center; gap: 6px; }
.form-options input[type="number"] { width: 70px; }
.error { color: #dc3545; margin-top: 8px; }
</style>
