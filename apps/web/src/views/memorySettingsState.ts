export interface MemoryPreferenceState {
  value: boolean | null
  loading: boolean
  readFailed: boolean
}

export function initialMemoryPreferenceState(): MemoryPreferenceState {
  return { value: null, loading: true, readFailed: false }
}

export function memoryPreferenceReadFailed(): MemoryPreferenceState {
  return { value: null, loading: false, readFailed: true }
}

export function memoryPreferenceLoaded(_previous: MemoryPreferenceState, value: boolean): MemoryPreferenceState {
  return { value, loading: false, readFailed: false }
}

export function createLatestRequestGuard() {
  let latest = 0
  return {
    begin() {
      latest += 1
      return latest
    },
    isCurrent(request: number) {
      return request === latest
    },
    invalidate() {
      latest += 1
    },
  }
}

export interface MemoryListStatus {
  initialLoading: boolean
  initialListError: string
  appendError: string
  loadingMore: boolean
}

export function createMemoryListCoordinator() {
  const requests = createLatestRequestGuard()
  return {
    begin: requests.begin,
    isCurrent: requests.isCurrent,
    invalidate: requests.invalidate,
    invalidateForSave: requests.invalidate,
    canAdd(initialLoading: boolean, initialListError: string) {
      return !initialLoading && !initialListError
    },
    stableAfterSave(): MemoryListStatus {
      return { initialLoading: false, initialListError: '', appendError: '', loadingMore: false }
    },
  }
}

export async function runConfirmedMemoryDelete(
  confirmDelete: () => boolean,
  deleteAction: () => Promise<void>,
): Promise<boolean> {
  if (!confirmDelete()) return false
  await deleteAction()
  return true
}

export interface MemoryRowLike {
  id: string
  category: string
}

export function syncMemoryAfterSave<T extends MemoryRowLike>(
  rows: T[],
  saved: T,
  selectedCategory?: string,
): T[] {
  if (selectedCategory && saved.category !== selectedCategory) {
    return rows.filter(row => row.id !== saved.id)
  }
  const index = rows.findIndex(row => row.id === saved.id)
  if (index < 0) return [saved, ...rows]
  return rows.map(row => row.id === saved.id ? saved : row)
}

export function nextAppendError(append: boolean, current: string): string {
  return append ? current : ''
}

export function appendRequestCursor(cursor: string | null): string | undefined {
  return cursor ?? undefined
}

export interface MemoryPageLike<T> {
  items: T[]
  next_cursor: string | null
}

export function appendMemoryPage<T>(rows: T[], page: MemoryPageLike<T>) {
  return { rows: [...rows, ...page.items], nextCursor: page.next_cursor }
}

export interface NativeDialogLike {
  open: boolean
  showModal(): void
  close(): void
}

export function showMemoryDialog(dialog: NativeDialogLike, focusFirst: () => void) {
  if (!dialog.open) dialog.showModal()
  focusFirst()
}

export function closeMemoryDialog(dialog: NativeDialogLike, restoreFocus: () => void) {
  if (dialog.open) dialog.close()
  restoreFocus()
}

export interface FocusableLike {
  focus(): void
}

export interface DialogTabEventLike {
  key: string
  shiftKey: boolean
  preventDefault(): void
}

export function trapDialogTabFocus(
  event: DialogTabEventLike,
  focusable: FocusableLike[],
  activeElement: unknown,
) {
  if (event.key !== 'Tab' || focusable.length === 0) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

export function restoreDialogTrigger(
  trigger: (FocusableLike & { isConnected?: boolean }) | null,
  fallback: FocusableLike | null,
) {
  ;(trigger?.isConnected ? trigger : fallback)?.focus()
}
