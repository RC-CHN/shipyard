import { computed } from 'vue'
import { ShipStatus } from '@/types/api'

export interface StatusBadgeProps {
  status: number
  size?: 'sm' | 'md' | 'lg'
}

export function useStatusBadge(props: StatusBadgeProps) {
  const statusConfig = computed(() => {
    switch (props.status) {
      case ShipStatus.RUNNING:
        return {
          text: 'Running',
          bgClass: 'bg-green-100',
          textClass: 'text-green-800',
          dotClass: 'bg-green-500',
        }
      case ShipStatus.STOPPED:
        return {
          text: 'Stopped',
          bgClass: 'bg-gray-100',
          textClass: 'text-gray-600',
          dotClass: 'bg-gray-400',
        }
      case ShipStatus.CREATING:
        return {
          text: 'Creating',
          bgClass: 'bg-yellow-100',
          textClass: 'text-yellow-800',
          dotClass: 'bg-yellow-500',
        }
      default:
        return {
          text: 'Unknown',
          bgClass: 'bg-gray-100',
          textClass: 'text-gray-600',
          dotClass: 'bg-gray-400',
        }
    }
  })

  const sizeClass = computed(() => {
    switch (props.size || 'md') {
      case 'sm':
        return 'px-2 py-0.5 text-xs'
      case 'lg':
        return 'px-4 py-2 text-base'
      default:
        return 'px-2.5 py-1 text-sm'
    }
  })

  return {
    statusConfig,
    sizeClass,
  }
}
