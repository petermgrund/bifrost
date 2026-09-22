<script>
  import { Button, Heading, Icon, LoadingSpinner, Text, modalManager, toastManager } from '@immich/ui';
  import { mdiBookmarkMultipleOutline, mdiImageAlbum, mdiPlus } from '@mdi/js';
  import { get, post } from '../lib/api.svelte.js';
  import { plural } from '../lib/format.js';
  import { loadCollections, store } from '../lib/store.svelte.js';
  import NewCollectionModal from './NewCollectionModal.svelte';
  import PickerPopover from './PickerPopover.svelte';

  let albums = $state(null);
  let albumQ = $state('');
  let importing = $state(false);

  const albumItems = $derived.by(() => {
    const q = albumQ.trim().toLowerCase();
    return (albums || [])
      .filter((a) => !q || a.name.toLowerCase().includes(q))
      .slice(0, 8)
      .map((a) => ({
        id: a.id,
        label: a.name || '(unnamed album)',
        sub: `${plural(a.count, 'photo')} · ${a.account}`,
        thumb: a.thumb,
        icon: mdiImageAlbum,
      }));
  });

  loadCollections();

  async function create() {
    const created = await modalManager.show(NewCollectionModal, {});
    if (!created) return;
    await loadCollections();
    window.location.hash = `#/collections/${created.id}`;
  }

  async function loadAlbums() {
    if (albums !== null) return;
    try {
      albums = await get('/photos/api/immich-albums');
    } catch (e) {
      albums = [];
      toastManager.danger(e.message);
    }
  }

  async function importAlbum(it) {
    importing = true;
    try {
      const c = await post('/photos/api/collections/import', { album_id: it.id });
      await loadCollections();
      toastManager.primary(`Imported ${plural(c.added, 'photo')} from ${it.label}`);
      window.location.hash = `#/collections/${c.id}`;
    } catch (e) {
      toastManager.danger(e.message);
    } finally {
      importing = false;
    }
  }
</script>

<div class="flex flex-col gap-6 p-4 md:p-6">
  <div class="flex flex-wrap items-center gap-3">
    <Heading size="medium" tag="h1" class="me-auto">Collections</Heading>
    <PickerPopover
      label="Import Immich album"
      icon={mdiImageAlbum}
      items={albumItems}
      bind:query={albumQ}
      placeholder="Search albums"
      empty={albums === null ? '' : 'No album matches'}
      loading={albums === null}
      disabled={importing}
      align="end"
      onOpen={loadAlbums}
      onPick={importAlbum}
    />
    {#if importing}<LoadingSpinner />{/if}
    <Button size="small" leadingIcon={mdiPlus} onclick={create}>Create collection</Button>
  </div>

  {#if store.collections === null}
    <div class="flex justify-center py-24"><LoadingSpinner size="large" /></div>
  {:else if !store.collections.length}
    <div class="flex flex-col items-center gap-3 py-24 text-gray-500">
      <Icon icon={mdiBookmarkMultipleOutline} size="3rem" />
      <Text>No collections yet</Text>
    </div>
  {:else}
    <div class="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-x-3 gap-y-5 sm:grid-cols-[repeat(auto-fill,minmax(12rem,1fr))] sm:gap-x-4 sm:gap-y-6">
      {#each store.collections as c (c.id)}
        <a
          href="#/collections/{c.id}"
          class="group outline-primary flex flex-col gap-2 rounded-xl outline-offset-4 focus-visible:outline-2"
        >
          <div class="bg-light-200 aspect-square overflow-hidden rounded-xl">
            {#if c.cover}
              <img
                src={c.cover}
                alt=""
                loading="lazy"
                class="size-full object-cover transition duration-300 group-hover:scale-[1.03]"
              />
            {:else}
              <div class="grid size-full place-items-center text-gray-400">
                <Icon icon={mdiBookmarkMultipleOutline} size="3rem" />
              </div>
            {/if}
          </div>
          <div class="min-w-0 px-1">
            <p class="group-hover:text-primary truncate font-medium">{c.name}</p>
            <p class="truncate text-sm text-gray-600 dark:text-gray-400">
              {plural(c.count, 'photo')}{c.description ? ` · ${c.description}` : ''}
            </p>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>
