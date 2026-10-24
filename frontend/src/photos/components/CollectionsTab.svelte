<script>
  import { IconButton, Text } from '@immich/ui';
  import { mdiBookmarkOutline, mdiBookmarkPlusOutline, mdiClose, mdiPlus } from '@mdi/js';
  import { plural } from '../lib/format.js';
  import { store } from '../lib/store.svelte.js';
  import ListCard from './ListCard.svelte';
  import ListRow from './ListRow.svelte';
  import PickerPopover from './PickerPopover.svelte';

  let { rec, busy, onAdd, onRemove, onGo } = $props();

  let ecQ = $state('');

  const mine = $derived(rec.collections || []);

  const matches = $derived.by(() => {
    const q = ecQ.trim().toLowerCase();
    const all = store.collections || [];
    const inRec = new Set(mine.map((c) => c.id));
    const items = all
      .filter((c) => !inRec.has(c.id) && (!q || c.name.toLowerCase().includes(q)))
      .slice(0, 6)
      .map((c) => ({ id: c.id, label: c.name, sub: plural(c.count, 'photo'), icon: mdiBookmarkOutline }));
    if (q && !all.some((c) => c.name.toLowerCase() === q)) {
      items.push({ id: '__new', label: `Create “${ecQ.trim()}”`, icon: mdiPlus, name: ecQ.trim() });
    }
    return items;
  });

  const count = (c) => (store.collections || []).find((x) => x.id === c.id)?.count;
</script>

<div class="flex flex-col gap-3">
  <div class="flex items-center gap-2">
    <Text size="small" color="muted" class="grow">
      {mine.length ? `In ${plural(mine.length, 'collection')}` : 'Not in a collection'}
    </Text>
    <PickerPopover
      label="Add to collection"
      icon={mdiBookmarkPlusOutline}
      items={matches}
      bind:query={ecQ}
      placeholder="Find or name a collection"
      empty={store.collections === null ? 'Loading collections…' : 'Type a name to create one'}
      disabled={!!busy}
      align="end"
      onPick={onAdd}
    />
  </div>
  {#if mine.length}
    <ListCard>
      {#each mine as c (c.id)}
        <ListRow icon={mdiBookmarkOutline}>
          {#snippet trailing()}
            <IconButton
              icon={mdiClose}
              size="small"
              shape="round"
              variant="ghost"
              color="secondary"
              aria-label="Remove from {c.name}"
              disabled={!!busy}
              onclick={() => onRemove(c)}
            />
          {/snippet}
          <a href="#/collections/{c.id}" class="hover:text-primary block truncate text-sm font-medium" onclick={onGo}>{c.name}</a>
          {#if count(c) !== undefined}
            <p class="truncate text-xs text-gray-600 dark:text-gray-400">{plural(count(c), 'photo')}</p>
          {/if}
        </ListRow>
      {/each}
    </ListCard>
  {/if}
</div>
