import { createRouter, createWebHistory } from 'vue-router'
import TaskDetail from './components/TaskDetail.vue'

const routes = [
  { path: '/', name: 'home' },
  { path: '/tasks/:id', name: 'task-detail', component: TaskDetail, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
