<template>
  <div class="card">
    <h2>📋 历史任务</h2>
    <p v-if="loading">加载中...</p>
    <p v-else-if="tasks.length === 0">暂无任务</p>
    <table v-else class="task-table">
      <thead>
        <tr>
          <th>状态</th>
          <th>研究问题</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="task in tasks" :key="task.task_id">
          <td>
            <span class="status-dot" :class="task.status"></span>
            <span class="badge" :class="`badge-${task.status}`">{{ task.status }}</span>
          </td>
          <td>
            <router-link :to="`/tasks/${task.task_id}`">{{ task.query }}</router-link>
          </td>
          <td>{{ formatTime(task.created_at) }}</td>
          <td>
            <button class="btn btn-danger" @click="remove(task.task_id)">删除</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listTasks, deleteTask } from '../api/index.js'

const tasks = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    tasks.value = await listTasks(20)
  } catch (e) {
    console.error('Failed to load tasks:', e)
  } finally {
    loading.value = false
  }
}

async function remove(taskId) {
  await deleteTask(taskId)
  tasks.value = tasks.value.filter(t => t.task_id !== taskId)
}

function formatTime(ts) {
  return new Date(ts * 1000).toLocaleString('zh-CN')
}

onMounted(load)
</script>

<style scoped>
.task-table { width: 100%; border-collapse: collapse; }
.task-table th, .task-table td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }
.task-table th { font-weight: 600; color: #555; font-size: 0.9rem; }
.task-table a { color: #1a73e8; text-decoration: none; }
.task-table a:hover { text-decoration: underline; }
</style>
