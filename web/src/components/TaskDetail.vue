<template>
  <div class="task-detail">
    <div class="task-header">
      <router-link to="/" class="back-link">&larr; 返回</router-link>
      <h1>{{ task.query || '加载中...' }}</h1>
      <span class="badge" :class="`badge-${taskStatus}`">{{ taskStatus }}</span>
    </div>

    <ProgressPanel
      :completedNodes="completedNodes"
      :currentNode="currentNode"
    />

    <PlanCard :plan="taskState.research_plan" />
    <SourcesTable :sources="taskState.sources || []" />
    <EvidenceList :evidences="taskState.evidences || []" />
    <ReviewPanel
      v-if="reviewData"
      :reviewData="reviewData"
      :taskId="id"
      @decision="onReviewSubmitted"
    />
    <CritiqueDashboard :critique="taskState.critique_result" :metrics="taskState.iteration_metrics" />
    <FinalReport v-if="taskState.final_report" :report="taskState.final_report" />

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { getTask, subscribeToTask } from '../api/index.js'
import ProgressPanel from './ProgressPanel.vue'
import PlanCard from './PlanCard.vue'
import SourcesTable from './SourcesTable.vue'
import EvidenceList from './EvidenceList.vue'
import CritiqueDashboard from './CritiqueDashboard.vue'
import FinalReport from './FinalReport.vue'
import ReviewPanel from './ReviewPanel.vue'

const props = defineProps({ id: String })

const task = ref({ query: '', status: 'pending' })
const taskState = reactive({})
const taskStatus = ref('loading')
const completedNodes = ref([])
const currentNode = ref(null)
const reviewData = ref(null)
const error = ref('')
let eventSource = null

function handleNodeStart(data) {
  currentNode.value = data.node
}

function handleNodeDone(data) {
  completedNodes.value.push(data.node)

  const node = data.node
  if (data.result) {
    if (node === 'plan' && data.result.research_plan) {
      taskState.research_plan = data.result.research_plan
    }
    if (node === 'research') {
      if (data.result.sources) taskState.sources = data.result.sources
      if (data.result.evidences) taskState.evidences = data.result.evidences
    }
    if (node === 'summary' && data.result.draft_summary) {
      taskState.draft_summary = data.result.draft_summary
    }
    if (node === 'critique' && data.result.critique_result) {
      taskState.critique_result = data.result.critique_result
      taskState.iteration_metrics = data.result.iteration_metrics
    }
    if (node === 'final' && data.result.final_report) {
      taskState.final_report = data.result.final_report
    }
  }

  if (node === 'final') {
    taskStatus.value = 'completed'
  }
}

function handleDone(_data) {
  taskStatus.value = 'completed'
}

function handleReviewRequired(data) {
  reviewData.value = data
  taskStatus.value = 'review_required'
}

function onReviewSubmitted(decision) {
  reviewData.value = null
  taskStatus.value = 'running'
}

function handleError(_e) {
  error.value = '执行出错'
  taskStatus.value = 'failed'
}

onMounted(async () => {
  try {
    const data = await getTask(props.id)
    task.value = data
    taskStatus.value = data.status

    if (data.state) {
      Object.assign(taskState, data.state)
    }

    if (data.status === 'pending' || data.status === 'running') {
      taskStatus.value = 'running'
      eventSource = subscribeToTask(props.id, {
        onTaskStarted: () => { taskStatus.value = 'running' },
        onNodeStart: handleNodeStart,
        onNodeDone: handleNodeDone,
        onReviewRequired: handleReviewRequired,
        onDone: handleDone,
        onError: handleError,
      })
    }
  } catch (e) {
    error.value = `加载任务失败: ${e.message}`
    taskStatus.value = 'failed'
  }
})

onUnmounted(() => {
  if (eventSource) eventSource.close()
})
</script>

<style scoped>
.task-detail { max-width: 960px; margin: 0 auto; }
.task-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
.task-header h1 { margin: 0; font-size: 1.4rem; flex: 1; }
.back-link { color: #1a73e8; text-decoration: none; font-size: 0.95rem; }
.back-link:hover { text-decoration: underline; }
.error { color: #dc3545; padding: 12px; background: #fff; border-radius: 8px; margin-top: 16px; }
</style>
