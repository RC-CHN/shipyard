import { useRouter } from 'vue-router'

export function useNotFound() {
  const router = useRouter()

  const goHome = () => {
    router.push('/')
  }

  const goBack = () => {
    router.back()
  }

  return {
    goHome,
    goBack,
  }
}
