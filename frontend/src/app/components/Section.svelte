<script>
  import { Alert, Button, CloseButton, Heading, IconButton, Input, LoadingSpinner, Text, toastManager } from '@immich/ui';
  import { mdiChevronLeft, mdiChevronRight, mdiMagnify, mdiSync } from '@mdi/js';
  import { get, post } from '../lib/api.svelte.js';
  import { mediaMatches, syncSummary } from '../lib/format.js';
  import { loadMedia } from '../lib/store.svelte.js';
  import MediaThumb from './MediaThumb.svelte';

  let { kind, title, items, onOpen, onCode, actions = undefined } = $props();

  const PAGE = 10;

  let q = $state('');
  let page = $state(0);
  let running = $state(false);
  let progress = $state(null);
  let failures = $state([]);

  const needle = $derived(q.trim().toLowerCase());
  const rows = $derived(items.filter((m) => mediaMatches(m, needle)));
  const pages = $derived(Math.max(1, Math.ceil(rows.length / PAGE)));
  const current = $derived(Math.min(page, pages - 1));
  const first = $derived(current * PAGE);

  $effect(() => {
    void needle;
    page = 0;
  });

  async function syncAll() {
    if (running) return;
    running = true;
    failures = [];
    const timer = setInterval(async () => {
      try {
        const { runs } = await get('/api/runs/active');
        progress = runs.find((r) => r.job === `sync.${kind}`) || null;
      } catch {
        progress = null;
      }
    }, 750);
    try {
      const r = await post(`/sync/api/${kind}`);
      failures = r.events;
      if (r.events.length) toastManager.warning(`${syncSummary(r.summary)}; ${r.events.length} failed`);
      else toastManager.primary(syncSummary(r.summary));
      await loadMedia();
    } catch (e) {
      failures = [{ detail: e.message }];
    } finally {
      clearInterval(timer);
      running = false;
      progress = null;
    }
  }
</script>

<section class="flex min-w-0 flex-col gap-3">
  <div class="flex min-h-10 shrink-0 flex-wrap items-center gap-2">
    <Heading size="small" tag="h2">{title}</Heading>
    <span class="me-auto font-mono text-sm text-gray-500 dark:text-gray-400">{items.length}</span>
    {@render actions?.()}
    <Button size="small" leadingIcon={mdiSync} disabled={running} onclick={syncAll}>Sync everything</Button>
  </div>

  {#if running}
    <div class="flex shrink-0 items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
      <LoadingSpinner size="small" />
      <span class="truncate">{progress?.detail || 'Syncing'}</span>
      {#if progress?.total}<span class="font-mono text-xs">{progress.done}/{progress.total}</span>{/if}
    </div>
  {/if}

  {#if failures.length}
    <div class="border-danger/40 immich-scrollbar flex max-h-32 shrink-0 items-start gap-2 overflow-y-auto rounded-xl border px-3 py-2">
      <ul class="min-w-0 flex-1 text-sm">
        {#each failures as f, i (i)}
          <li class="py-0.5">
            {#if f.gramps_id}<span class="font-mono text-xs">{f.gramps_id}</span>{/if}
            {#if f.title}<span class="font-medium">{f.title}</span>{/if}
            <Text size="small" color="danger" class="inline">{f.detail}</Text>
          </li>
        {/each}
      </ul>
      <CloseButton size="small" onclick={() => (failures = [])} />
    </div>
  {/if}

  <div class="shrink-0">
    <Input
      bind:value={q}
      size="small"
      shape="round"
      leadingIcon={mdiMagnify}
      placeholder="Search"
      aria-label="Search {title}"
    />
  </div>

  {#if rows.length}
    <ul
      class="grid max-h-[40rem] min-h-[27.5rem] flex-[1_1_0] grid-rows-[repeat(10,minmax(0,1fr))] divide-y divide-gray-200 rounded-xl border border-gray-200 lg:min-h-[20rem] dark:divide-white/10 dark:border-white/10"
    >
      {#each rows.slice(first, first + PAGE) as m (m.code)}
        <li class="flex min-h-0 items-center gap-3 overflow-hidden px-3 py-1">
          <button
            type="button"
            class="ring-primary flex h-full min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg text-start outline-none focus-visible:ring-2 focus-visible:ring-inset"
            onclick={() => onOpen(m)}
          >
            <MediaThumb item={m} class="aspect-square h-full max-h-12 w-auto" />
            <span class="min-w-0 flex-1 truncate text-sm font-medium">{m.title || 'No title'}</span>
            {#if m.attention}<span class="text-danger shrink-0 text-xs">{m.attention}</span>{/if}
            {#if m.date}
              <span class="hidden max-w-[40%] shrink-0 truncate text-xs text-gray-500 sm:inline dark:text-gray-400">{m.date}</span>
            {/if}
          </button>
          <button
            type="button"
            class="bg-primary/10 text-primary hover:bg-primary/20 ring-primary shrink-0 cursor-pointer rounded-full px-2.5 py-1 font-mono text-xs font-medium transition-colors outline-none focus-visible:ring-2"
            aria-label="Manage {m.code}"
            onclick={() => onCode(m)}
          >
            {m.code}
          </button>
        </li>
      {/each}
    </ul>
    <div class="flex shrink-0 items-center justify-end gap-1">
      <span class="pe-1 font-mono text-xs text-gray-600 dark:text-gray-400">
        {first + 1}–{Math.min(first + PAGE, rows.length)} of {rows.length}
      </span>
      <IconButton
        icon={mdiChevronLeft}
        size="small"
        shape="round"
        variant="ghost"
        color="secondary"
        aria-label="Previous page"
        disabled={current === 0}
        onclick={() => (page = current - 1)}
      />
      <IconButton
        icon={mdiChevronRight}
        size="small"
        shape="round"
        variant="ghost"
        color="secondary"
        aria-label="Next page"
        disabled={current >= pages - 1}
        onclick={() => (page = current + 1)}
      />
    </div>
  {:else}
    <Alert color="secondary" title={items.length ? 'Nothing matches' : 'Nothing synced yet'} />
  {/if}
</section>
