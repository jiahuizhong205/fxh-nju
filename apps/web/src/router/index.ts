import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
    },
    {
      path: '/course-planning',
      name: 'course-planning',
      component: () => import('../views/CoursePlanningView.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('../views/KnowledgeView.vue'),
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
    },
    {
      path: '/recommend',
      name: 'recommend',
      component: () => import('../views/RecommendView.vue'),
    },
    {
      path: '/tutor',
      name: 'tutor',
      component: () => import('../views/TutorView.vue'),
    },
    {
      path: '/career',
      name: 'career',
      component: () => import('../views/CareerView.vue'),
    },
    {
      path: '/job/:id',
      name: 'job-detail',
      component: () => import('../views/JobDetailView.vue'),
    },
    {
      path: '/minor-report',
      name: 'minor-report',
      component: () => import('../views/MinorAnalysisReportView.vue'),
    },
    {
      path: '/time-preference',
      name: 'time-preference',
      component: () => import('../views/TimePreferenceView.vue'),
    },
    {
      path: '/conflict-resolution',
      name: 'conflict-resolution',
      component: () => import('../views/ConflictResolutionView.vue'),
    },
    {
      path: '/edit-profile',
      name: 'edit-profile',
      component: () => import('../views/EditProfileView.vue'),
    },
    {
      path: '/interest-selection',
      name: 'interest-selection',
      component: () => import('../views/InterestSelectionView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue'),
    },
    {
      path: '/settings/bind-contact',
      name: 'bind-contact',
      component: () => import('../views/BindContactView.vue'),
    },
    {
      path: '/settings/notification',
      name: 'notification-settings',
      component: () => import('../views/NotificationSettingsView.vue'),
    },
    {
      path: '/settings/switch-account',
      name: 'switch-account',
      component: () => import('../views/SwitchAccountView.vue'),
    },
    {
      path: '/settings/learning-reminder',
      name: 'learning-reminder',
      component: () => import('../views/LearningReminderView.vue'),
    },
    {
      path: '/settings/job-push',
      name: 'job-push',
      component: () => import('../views/JobPushPreferencesView.vue'),
    },
    {
      path: '/settings/clear-cache',
      name: 'clear-cache',
      component: () => import('../views/ClearCacheView.vue'),
    },
    {
      path: '/settings/data-sync',
      name: 'data-sync',
      component: () => import('../views/DataSyncView.vue'),
    },
    {
      path: '/settings/about',
      name: 'about',
      component: () => import('../views/AboutView.vue'),
    },
    {
      path: '/settings/learning-progress',
      name: 'learning-progress',
      component: () => import('../views/LearningProgressView.vue'),
    },
    {
      path: '/settings/change-password',
      name: 'change-password',
      component: () => import('../views/ChangePasswordView.vue'),
    },
    {
      path: '/settings/feedback',
      name: 'feedback',
      component: () => import('../views/FeedbackView.vue'),
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('fxh_token')
  if (to.name !== 'login' && !token) return { name: 'login' }
  if (to.name === 'login' && token) return { name: 'home' }
})

export default router
