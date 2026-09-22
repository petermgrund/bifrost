<script>
  import { Alert, Badge, Button, ContextMenuButton, Input, MenuItemType, Text } from '@immich/ui';
  import {
    mdiImagePlusOutline,
    mdiImageRemoveOutline,
    mdiPencilOutline,
    mdiStarOutline,
    mdiSync,
    mdiTrayArrowUp,
  } from '@mdi/js';
  import { plural, sizeText } from '../lib/format.js';
  import { searchAssets } from '../lib/store.svelte.js';
  import PickerPopover from './PickerPopover.svelte';

  let { rec, busy, onAdd, onMatch, onPromote, onRemove, onLabel, onView, onError } = $props();

  let verQ = $state('');
  let found = $state([]);
  let editLabel = $state(null);
  let labelDraft = $state('');
  let labelRef = $state(null);
  let fileInput = $state(null);
  let timer;

  const UPLOAD = { id: '__upload', label: 'Upload a new image', icon: mdiTrayArrowUp };

  const members = $derived(rec.versions?.members || []);
  const suggestions = $derived(rec.suggestions || []);
  const verItems = $derived(verQ.trim() ? found.map(candidate) : [UPLOAD]);

  $effect(() => {
    if (editLabel && labelRef) labelRef.focus();
  });

  function blocker(c) {
    if (c.in_stack || c.versions > 1) return 'Already stacked with other photos';
    if (c.owner_id && rec.owner_id && c.owner_id !== rec.owner_id) return 'Belongs to another Immich account';
    if (rec.gramps && c.gramps_id && c.gramps_id !== rec.gramps.gramps_id) return `Also in Gramps, as ${c.gramps_id}`;
    return '';
  }

  function candidate(card) {
    const why = blocker(card);
    const sub = [card.title && card.filename, card.gramps_id && `in Gramps as ${card.gramps_id}`];
    return {
      id: card.asset_id,
      label: card.title || card.filename,
      sub: why || sub.filter(Boolean).join(' · '),
      thumb: card.thumb,
      disabled: !!why,
      card,
    };
  }

  function onQuery(value) {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = value.trim();
      if (!q) {
        found = [];
        return;
      }
      try {
        const skip = new Set([rec.asset_id, ...members.map((m) => m.asset_id)]);
        const results = await searchAssets(q, skip);
        if (verQ.trim() === q) found = results.slice(0, 8);
      } catch (e) {
        onError(e.message);
      }
    }, 250);
  }

  function picked(it) {
    if (it.id === UPLOAD.id) fileInput.click();
    else onAdd(it.card);
  }

  function chosen(e) {
    const file = e.currentTarget.files?.[0];
    e.currentTarget.value = '';
    if (!file) return;
    onAdd({ asset_id: UPLOAD.id, filename: file.name, title: '', thumb: URL.createObjectURL(file), size: file.size, file });
  }

  function startLabel(m) {
    setTimeout(() => {
      editLabel = m.asset_id;
      labelDraft = m.label || '';
    }, 150);
  }

  function saveLabel(m) {
    if (editLabel !== m.asset_id) return;
    editLabel = null;
    const label = labelDraft.trim();
    if (label !== (m.label || '')) onLabel(m, label);
  }

  function menu(m) {
    const note = { title: m.label ? 'Edit note' : 'Add note', icon: mdiPencilOutline, onAction: () => startLabel(m) };
    if (m.is_primary) return [note];
    return [
      { title: 'Make main', icon: mdiStarOutline, onAction: () => onPromote(m) },
      m.drift?.length ? { title: 'Match to main', icon: mdiSync, onAction: () => onMatch(m) } : undefined,
      note,
      MenuItemType.Divider,
      { title: 'Remove from versions', icon: mdiImageRemoveOutline, color: 'danger', onAction: () => onRemove(m) },
    ];
  }
</script>

<div class="flex h-full min-h-0 flex-col gap-3">
  <div class="flex items-center gap-2">
    <Text size="small" color="muted" class="grow">
      {members.length > 1 ? plural(members.length, 'version') : 'No other versions'}
    </Text>
    <PickerPopover
      label="Add version"
      icon={mdiImagePlusOutline}
      items={verItems}
      bind:query={verQ}
      {onQuery}
      placeholder="Search titles and file names"
      empty={verQ.trim() ? 'No photo matches' : ''}
      disabled={!!busy}
      align="end"
      onPick={picked}
    />
    <input bind:this={fileInput} type="file" accept="image/*" class="hidden" onchange={chosen} />
  </div>

  {#if rec.versions?.error}
    <Alert color="danger" size="small" title={rec.versions.error} />
  {/if}

  <div class="immich-scrollbar min-h-0 flex-1 overflow-y-auto">
    {#if members.length}
      <ul class="flex flex-col divide-y divide-gray-200 rounded-xl border border-gray-200 dark:divide-white/10 dark:border-white/10">
        {#each members as m (m.asset_id)}
          <li class="flex items-center gap-3 px-3 py-2">
            <button type="button" class="shrink-0 cursor-zoom-in" title="View larger" onclick={() => onView(m)}>
              <img src={m.thumb} alt="" class="size-12 rounded-lg object-cover" />
            </button>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <p class="truncate text-sm font-medium">{m.filename}</p>
                {#if m.is_primary}<Badge size="tiny" color="primary" shape="round">Main</Badge>{/if}
              </div>
              {#if editLabel === m.asset_id}
                <Input
                  bind:ref={labelRef}
                  bind:value={labelDraft}
                  size="tiny"
                  placeholder="Note about this version"
                  class="mt-1 max-w-sm"
                  onkeydown={(e) => {
                    if (e.key === 'Enter') saveLabel(m);
                    else if (e.key === 'Escape') {
                      e.stopPropagation();
                      editLabel = null;
                    }
                  }}
                  onblur={() => saveLabel(m)}
                />
              {:else}
                <p class="flex min-w-0 gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                  <span class="shrink-0 font-mono">{sizeText(m)}</span>
                  {#if m.label}<span>·</span><span class="truncate italic">{m.label}</span>{/if}
                </p>
              {/if}
              {#if !m.is_primary && m.drift?.length}
                <p class="text-warning-700 truncate text-xs" title="Compared with the main image">
                  Differs: {m.drift.join(', ')}
                </p>
              {/if}
            </div>
            <ContextMenuButton aria-label="Actions for {m.filename}" items={menu(m)} disabled={!!busy} />
          </li>
        {/each}
      </ul>
    {/if}

    {#if suggestions.length}
      <p class="mt-5 mb-1 px-1 text-xs font-medium text-gray-600 dark:text-gray-400">Suggestions</p>
      <ul class="flex flex-col">
        {#each suggestions as sg (sg.asset_id)}
          {@const why = blocker(sg)}
          <li class="hover:bg-light-100 flex items-center gap-3 rounded-xl px-3 py-1.5">
            <button type="button" class="shrink-0 cursor-zoom-in" title="View larger" onclick={() => onView(sg)}>
              <img src={sg.thumb} alt="" class="size-10 rounded-lg object-cover" />
            </button>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm">{sg.title || sg.filename}</p>
              <p class="truncate text-xs text-gray-600 dark:text-gray-400">{why || sg.why}</p>
            </div>
            <Button size="tiny" variant="outline" color="secondary" disabled={!!busy || !!why} onclick={() => onAdd(sg)}>
              Add
            </Button>
          </li>
        {/each}
      </ul>
    {/if}
  </div>
</div>
