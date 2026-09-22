<script>
  import { IconButton } from '@immich/ui';
  import { mdiBookmarkOutline, mdiBookmarkPlusOutline, mdiClose, mdiPlus } from '@mdi/js';
  import { plural } from '../lib/format.js';
  import { store } from '../lib/store.svelte.js';
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
</script>

<div class="flex flex-col gap-3">
  <div class="flex flex-wrap items-center gap-3">
    <PickerPopover
      label="Add to collection"
      icon={mdiBookmarkPlusOutline}
      items={matches}
      bind:query={ecQ}
      placeholder="Find or name a collection"
      empty={store.collections === null ? 'Loading collections…' : 'Type a name to create one'}
      disabled={!!busy}
      onPick={onAdd}
    />
  </div>
  {#if mine.length}
    <ul class="flex flex-col">
      {#each mine as c (c.id)}
        <li class="hover:bg-light-100 flex items-center gap-2 rounded-xl px-3 py-1">
          <a href="#/collections/{c.id}" class="hover:text-primary grow truncate text-sm" onclick={onGo}>{c.name}</a>
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
        </li>
      {/each}
    </ul>
  {/if}
</div>
