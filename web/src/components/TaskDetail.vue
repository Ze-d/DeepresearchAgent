<template>
  <div class="card">
    <h2>Task Detail</h2>
    <p>Task ID: {{ id }}</p>
    <router-link to="/">← 返回</router-link>
  </div>
</template>

<script setup>
defineProps({ id: String })
</script>
