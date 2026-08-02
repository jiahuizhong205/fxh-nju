import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
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
  ],
})

export default router
