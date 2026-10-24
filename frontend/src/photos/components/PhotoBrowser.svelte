<script>
  import { Alert, Badge, Button, Heading, Icon, LoadingSpinner, Text } from '@immich/ui';
  import { mdiImageMultipleOutline, mdiMagnify } from '@mdi/js';
  import { untrack } from 'svelte';
  import { get, qs } from '../lib/api.svelte.js';
  import { cardFrom, plural } from '../lib/format.js';
  import { onRecord } from '../lib/store.svelte.js';
  import PhotoTile from './PhotoTile.svelte';

  let { mode, q, person, onClearQuery, onOpenPhoto } = $props();

  const TITLES = { recent: 'Recent', synced: 'In Gramps' };

  let items = $state([]);
  let nextPage = $state(null);
  let loading = $state(false);
  let error = $state('');
  let atEnd = $state(false);
  let token = 0;

  $effect(() => {
    void [mode, q, person];
    untrack(() => load(true));
  });

  $effect(() => {
    if (atEnd && nextPage && !loading && !error) untrack(() => load(false));
  });

  $effect(() =>
    onRecord((rec, replacing) => {
      const old = replacing || rec.asset_id;
      const seen = new Set();
      items = items
        .map((i) => (i.asset_id === old ? { ...i, ...cardFrom(rec) } : i))
        .filter((i) => !seen.has(i.asset_id) && seen.add(i.asset_id));
    }),
  );

  async function load(reset) {
    const page = reset ? 1 : nextPage;
    if (!page || (loading && !reset)) return;
    const mine = ++token;
    loading = true;
    error = '';
    if (reset) {
      items = [];
      nextPage = null;
    }
    try {
      const r = await get(`/photos/api/search?${qs({ mode, page, q, person: person?.id })}`);
      if (mine !== token) return;
      const seen = new Set(items.map((i) => i.asset_id));
      items = [...items, ...r.items.filter((i) => !seen.has(i.asset_id))];
      nextPage = r.nextPage;
    } catch (e) {
      if (mine === token) error = e.message;
    } finally {
      if (mine === token) loading = false;
    }
  }

  function scroller(node) {
    for (let el = node.parentElement; el; el = el.parentElement) {
      if (/auto|scroll/.test(getComputedStyle(el).overflowY)) return el;
    }
    return null;
  }

  function watchEnd(node) {
    const observer = new IntersectionObserver((entries) => (atEnd = entries[0].isIntersecting), {
      root: scroller(node),
      rootMargin: '800px 0px',
    });
    observer.observe(node);
    return () => observer.disconnect();
  }
</script>

<div class="flex flex-col gap-4 p-4 md:p-6">
  <div class="flex flex-wrap items-center gap-3">
    <Heading size="medium" tag="h1" class="me-auto">{TITLES[mode]}</Heading>
    {#if q}
      <Badge color="secondary" shape="round" leadingIcon={mdiMagnify} onClose={onClearQuery}>{q}</Badge>
    {/if}
  </div>

  {#if error}
    <Alert color="danger" title={error} />
  {/if}

  {#if !items.length && !loading && !error}
    <div class="flex flex-col items-center gap-3 py-24 text-gray-500">
      <Icon icon={mdiImageMultipleOutline} size="3rem" />
      <Text>{q ? `No photos match “${q}”` : 'No photos here'}</Text>
    </div>
  {:else}
    <div class="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2 sm:grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] sm:gap-3">
      {#each items as it (it.asset_id)}
        <PhotoTile item={it} onOpen={() => onOpenPhoto(it.asset_id)} />
      {/each}
    </div>
  {/if}

  <div class="flex min-h-10 items-center justify-center gap-4" {@attach watchEnd}>
    {#if loading}
      <LoadingSpinner size="large" />
    {:else if nextPage && error}
      <Button size="small" variant="outline" color="secondary" onclick={() => load(false)}>Load more</Button>
    {/if}
    {#if items.length}
      <Text size="small" color="muted">{plural(items.length, 'photo')} shown</Text>
    {/if}
  </div>
</div>
