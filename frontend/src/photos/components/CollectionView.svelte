<script>
  import {
    Alert,
    ContextMenuButton,
    Icon,
    IconButton,
    LoadingSpinner,
    Text,
    Textarea,
    modalManager,
    toastManager,
  } from '@immich/ui';
  import { mdiArrowLeft, mdiClose, mdiDeleteOutline, mdiImageMultipleOutline, mdiImagePlusOutline } from '@mdi/js';
  import { tick, untrack } from 'svelte';
  import { flip } from 'svelte/animate';
  import { del, get, post, put } from '../lib/api.svelte.js';
  import { assetItem, cardFrom, plural } from '../lib/format.js';
  import { loadCollections, onRecord, searchAssets } from '../lib/store.svelte.js';
  import PhotoTile from './PhotoTile.svelte';
  import PickerPopover from './PickerPopover.svelte';
  import PositionInput from './PositionInput.svelte';

  let { id, onOpenPhoto } = $props();

  let col = $state(null);
  let error = $state('');
  let name = $state('');
  let description = $state('');
  let dragId = $state(null);
  let flash = $state(null);
  let addQ = $state('');
  let addItems = $state([]);
  let orderBefore = '';
  let fromField = false;
  let searchTimer;
  let flashTimer;

  $effect(() => {
    void id;
    untrack(() => {
      col = null;
      load();
    });
  });

  $effect(() =>
    onRecord((rec, replacing) => {
      if (!col) return;
      const old = replacing || rec.asset_id;
      const here = col.items.some((i) => i.asset_id === old || i.asset_id === rec.asset_id);
      const member = (rec.collections || []).some((c) => c.id === col.id);
      if (here && !member) {
        col.items = col.items.filter((i) => i.asset_id !== old && i.asset_id !== rec.asset_id);
      } else if (!here && member) {
        load();
      } else if (here) {
        const seen = new Set();
        col.items = col.items
          .map((i) => (i.asset_id === old ? { ...i, ...cardFrom(rec) } : i))
          .filter((i) => !seen.has(i.asset_id) && seen.add(i.asset_id));
      }
    }),
  );

  async function load() {
    const wanted = id;
    error = '';
    try {
      const c = await get(`/photos/api/collections/${wanted}`);
      if (wanted !== id) return;
      col = c;
      name = c.name;
      description = c.description || '';
    } catch (e) {
      if (wanted === id) error = e.message;
    }
  }

  async function saveMeta() {
    if (!col) return;
    const cid = col.id;
    const n = name.trim();
    const d = description.trim();
    if (!n) {
      name = col.name;
      toastManager.warning('A collection needs a name');
      return;
    }
    if (n === col.name && d === (col.description || '')) return;
    try {
      const c = await put(`/photos/api/collections/${cid}`, { name: n, description: d });
      loadCollections();
      toastManager.primary('Collection updated');
      if (col?.id !== cid) return;
      col.name = c.name;
      col.description = c.description;
      if (name.trim() === n) name = c.name;
      if (description.trim() === d) description = c.description || '';
    } catch (e) {
      toastManager.danger(e.message);
    }
  }

  async function deleteCollection() {
    const cid = col.id;
    const label = col.name;
    const confirmed = await modalManager.showDialog({
      title: 'Delete collection',
      prompt: `Delete “${label}”? Its photos stay in Immich.`,
      confirmText: 'Delete',
      icon: mdiDeleteOutline,
    });
    if (!confirmed) return;
    try {
      await del(`/photos/api/collections/${cid}`);
      await loadCollections();
      toastManager.primary(`Deleted ${label}`);
      window.location.hash = '#/collections';
    } catch (e) {
      toastManager.danger(e.message);
    }
  }

  function onAddQuery(value) {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(async () => {
      const q = value.trim();
      if (!q || !col) {
        addItems = [];
        return;
      }
      try {
        const found = await searchAssets(q, new Set(col.items.map((i) => i.asset_id)));
        if (addQ.trim() === q) addItems = found.slice(0, 8).map(assetItem);
      } catch (e) {
        toastManager.danger(e.message);
      }
    }, 250);
  }

  async function addPhoto(it) {
    const cid = col.id;
    addItems = addItems.filter((x) => x.id !== it.id);
    try {
      const c = await post(`/photos/api/collections/${cid}/items`, { asset_ids: [it.id] });
      loadCollections();
      toastManager.primary(`Added to ${c.name}`);
      if (col?.id === cid) col.items = c.items;
    } catch (e) {
      toastManager.danger(e.message);
    }
  }

  async function removeItem(it) {
    const cid = col.id;
    const label = col.name;
    col.items = col.items.filter((i) => i.asset_id !== it.asset_id);
    try {
      await del(`/photos/api/collections/${cid}/items/${it.asset_id}`);
      loadCollections();
      toastManager.primary(`Removed from ${label}`);
    } catch (e) {
      toastManager.danger(e.message);
      if (col?.id === cid) load();
    }
  }

  function applyOrder(ids) {
    const byId = new Map(col.items.map((i) => [i.asset_id, i]));
    const listed = new Set(ids);
    col.items = [...ids.map((a) => byId.get(a)).filter(Boolean), ...col.items.filter((i) => !listed.has(i.asset_id))];
  }

  async function highlight(assetId) {
    flash = assetId;
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => (flash = null), 1600);
    await tick();
    document
      .querySelector(`[data-asset="${CSS.escape(assetId)}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  async function moveTo(it, position) {
    const cid = col.id;
    const items = col.items.filter((i) => i.asset_id !== it.asset_id);
    items.splice(position - 1, 0, it);
    col.items = items;
    highlight(it.asset_id);
    try {
      const r = await put(`/photos/api/collections/${cid}/items/${it.asset_id}/position`, { position });
      loadCollections();
      if (col?.id === cid) applyOrder(r.asset_ids);
    } catch (e) {
      toastManager.danger(e.message);
      if (col?.id === cid) load();
    }
  }

  function onDragStart(e, it) {
    if (fromField) {
      e.preventDefault();
      return;
    }
    dragId = it.asset_id;
    orderBefore = col.items.map((i) => i.asset_id).join(',');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', it.asset_id);
  }

  function onDragOver(e, it) {
    if (!dragId) return;
    e.preventDefault();
    if (dragId === it.asset_id) return;
    const items = [...col.items];
    const from = items.findIndex((i) => i.asset_id === dragId);
    const to = items.findIndex((i) => i.asset_id === it.asset_id);
    if (from < 0 || to < 0) return;
    const [moved] = items.splice(from, 1);
    items.splice(to, 0, moved);
    col.items = items;
  }

  async function finishDrag() {
    if (!dragId) return;
    dragId = null;
    const cid = col.id;
    const ids = col.items.map((i) => i.asset_id);
    if (ids.join(',') === orderBefore) return;
    try {
      const r = await put(`/photos/api/collections/${cid}/order`, { asset_ids: ids });
      loadCollections();
      if (col?.id === cid) applyOrder(r.asset_ids);
    } catch (e) {
      toastManager.danger(e.message);
      if (col?.id === cid) load();
    }
  }
</script>

<div class="flex flex-col gap-5 p-4 md:p-6">
  {#if error}
    <Alert color="danger" title={error} />
  {:else if !col}
    <div class="flex justify-center py-24"><LoadingSpinner size="large" /></div>
  {:else}
    <div class="flex flex-wrap items-start gap-2">
      <IconButton
        icon={mdiArrowLeft}
        href="#/collections"
        shape="round"
        variant="ghost"
        color="secondary"
        aria-label="Back to collections"
        class="mt-1 shrink-0"
      />
      <div class="min-w-0 flex-1 basis-60">
        <input
          bind:value={name}
          aria-label="Collection name"
          class="focus:border-primary w-full truncate border-b-2 border-transparent bg-transparent pb-1 text-3xl font-bold tracking-tight transition-colors outline-none hover:border-gray-300 dark:hover:border-gray-600"
          onblur={saveMeta}
          onkeydown={(e) => {
            if (e.key === 'Enter') e.currentTarget.blur();
            else if (e.key === 'Escape') {
              name = col.name;
              e.currentTarget.blur();
            }
          }}
        />
        <Textarea
          variant="ghost"
          bind:value={description}
          placeholder="Add a description"
          class="mt-2 text-gray-700 dark:text-gray-300"
          onblur={saveMeta}
        />
        <Text size="small" color="muted" class="mt-1">{plural(col.items.length, 'photo')}</Text>
      </div>
      <div class="ms-auto flex shrink-0 items-center gap-1 pt-1">
        <PickerPopover
          label="Add photos"
          icon={mdiImagePlusOutline}
          items={addItems}
          bind:query={addQ}
          onQuery={onAddQuery}
          keepOpen
          placeholder="Search titles and file names"
          empty={addQ.trim() ? 'No photo matches' : ''}
          align="end"
          onPick={addPhoto}
        />
        <ContextMenuButton
          aria-label="Collection actions"
          items={[{ title: 'Delete collection', icon: mdiDeleteOutline, color: 'danger', onAction: deleteCollection }]}
        />
      </div>
    </div>

    {#if col.items.length}
      <div class="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-2 sm:grid-cols-[repeat(auto-fill,minmax(11rem,1fr))] sm:gap-3" role="list">
        {#each col.items as it, i (it.asset_id)}
          <div
            role="listitem"
            data-asset={it.asset_id}
            draggable="true"
            class={['cursor-grab transition-opacity', dragId === it.asset_id && 'opacity-40']}
            animate:flip={{ duration: dragId ? 0 : 250 }}
            onpointerdown={(e) => (fromField = !!e.target.closest('input, button, a'))}
            ondragstart={(e) => onDragStart(e, it)}
            ondragover={(e) => onDragOver(e, it)}
            ondrop={(e) => {
              e.preventDefault();
              finishDrag();
            }}
            ondragend={finishDrag}
          >
            <PhotoTile item={it} highlight={flash === it.asset_id} onOpen={() => onOpenPhoto(it.asset_id)}>
              {#snippet topLeft()}
                <PositionInput
                  position={i + 1}
                  max={col.items.length}
                  label={it.title || it.filename}
                  onMove={(n) => moveTo(it, n)}
                />
              {/snippet}
              {#snippet topRight()}
                <IconButton
                  icon={mdiClose}
                  size="tiny"
                  shape="round"
                  color="secondary"
                  class="bg-black/55 text-white backdrop-blur-sm not-disabled:hover:bg-black/75"
                  aria-label="Remove from collection"
                  onclick={() => removeItem(it)}
                />
              {/snippet}
            </PhotoTile>
          </div>
        {/each}
      </div>
    {:else}
      <div class="flex flex-col items-center gap-3 py-24 text-gray-500">
        <Icon icon={mdiImageMultipleOutline} size="3rem" />
        <Text>No photos in this collection yet</Text>
      </div>
    {/if}
  {/if}
</div>
