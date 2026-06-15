<template>
  <div id="app-container">
    <header class="app-header">
      <h1>🔍 DeepResearch Agent</h1>
      <p>基于 LangGraph + DeepSeek 的深度调研智能体</p>
    </header>
    <main>
      <router-view v-if="$route.name === 'task-detail'" />
      <div v-else class="home">
        <TaskForm />
        <TaskList />
      </div>
    </main>
  </div>
</template>

<script setup>
import TaskForm from './components/TaskForm.vue'
import TaskList from './components/TaskList.vue'
</script>

<style scoped>
.app-header {
  text-align: center;
  padding: 24px 0 8px;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 24px;
}
.app-header h1 { margin: 0; font-size: 1.8rem; }
.app-header p { margin: 4px 0 0; color: #666; }
.home { max-width: 900px; margin: 0 auto; }
</style>
