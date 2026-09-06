import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchAvatar, uploadAvatar } from '../api/client'

const DEFAULT_AVATAR = '/illustrations/avatar-wreath.png'

export const useAvatarStore = defineStore('avatar', () => {
  const avatarUrl = ref(DEFAULT_AVATAR)
  const loading = ref(false)
  let objectUrl = ''

  function replaceObjectUrl(blob: Blob) {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    objectUrl = URL.createObjectURL(blob)
    avatarUrl.value = objectUrl
  }

  async function load() {
    loading.value = true
    try {
      const blob = await fetchAvatar()
      if (blob) replaceObjectUrl(blob)
      else reset()
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File) {
    await uploadAvatar(file)
    await load()
  }

  function reset() {
    if (objectUrl) URL.revokeObjectURL(objectUrl)
    objectUrl = ''
    avatarUrl.value = DEFAULT_AVATAR
  }

  return { avatarUrl, loading, load, upload, reset }
})
