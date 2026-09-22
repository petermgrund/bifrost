<script>
  import { Alert, Button, CloseButton, LoadingSpinner, Text, toastManager } from '@immich/ui';
  import { mdiContentSaveOutline, mdiSync } from '@mdi/js';
  import { Dialog, Tabs } from 'bits-ui';
  import { untrack } from 'svelte';
  import { del, get, post, put, qs, upload } from '../lib/api.svelte.js';
  import { dateProblem, formFrom, formKey, payload, savedForm } from '../lib/format.js';
  import { loadCollections, recordChanged } from '../lib/store.svelte.js';
  import AddVersionDialog from './AddVersionDialog.svelte';
  import CollectionsTab from './CollectionsTab.svelte';
  import DetailsTab from './DetailsTab.svelte';
  import Lightbox from './Lightbox.svelte';
  import VersionsTab from './VersionsTab.svelte';

  let { assetId, onClose } = $props();

  let rec = $state(null);
  let form = $state(null);
  let saved = $state('');
  let presented = $state('');
  let recError = $state('');
  let busy = $state('');
  let status = $state(null);
  let tab = $state('details');
  let lightbox = $state(null);
  let adding = $state(null);
  let content = $state(null);

  const unsaved = $derived(!!form && formKey(form) !== saved);
  const edited = $derived(!!form && formKey(form) !== presented);
  const problem = $derived(form ? dateProblem(form.date) : '');
  const syncable = $derived(!!rec && (!!rec.gramps || rec.sync.media));

  const tabs = $derived.by(() => {
    if (!rec) return [];
    const versions = rec.versions?.members?.length || 0;
    const cols = rec.collections?.length || 0;
    return [
      { id: 'details', label: 'Details' },
      { id: 'versions', label: versions > 1 ? `Versions (${versions})` : 'Versions' },
      { id: 'people', label: rec.people.length ? `People (${rec.people.length})` : 'People' },
      { id: 'collections', label: cols ? `Collections (${cols})` : 'Collections' },
    ];
  });

  $effect(() => {
    const id = assetId;
    untrack(() => load(id));
  });

  function setForm(f) {
    form = f;
    presented = formKey(f);
  }

  async function load(id) {
    try {
      const r = await get(`/photos/api/photo/${id}`);
      rec = r;
      saved = formKey(savedForm(r));
      setForm(formFrom(r));
    } catch (e) {
      recError = e.message;
    }
  }

  function applyRecord(r, replacing = null, keep = false) {
    const keepEdits = keep && edited;
    rec = r;
    saved = formKey(savedForm(r));
    if (!keepEdits) setForm(formFrom(r, keep));
    recordChanged(r, replacing);
  }

  function fail(e) {
    status = { kind: 'error', msg: e.message };
  }

  function succeed(msg) {
    status = null;
    toastManager.primary(msg);
  }

  function syncSummary(r) {
    const s = r.summary || {};
    const parts = [];
    if (s.created) parts.push(`created ${s.gramps_id}`);
    for (const e of r.events || []) {
      if (e.action === 'failed') parts.push(e.detail);
      else if (e.entity === 'media' && e.action === 'updated') parts.push(`updated ${Object.keys(e.data?.cols || {}).join(', ')}`);
      else if (e.entity === 'place' && (e.action === 'created' || e.action === 'updated')) parts.push(`place ${e.title}`);
      else if (e.entity === 'note' && (e.action === 'created' || e.action === 'updated')) parts.push(`note ${e.action}`);
    }
    if (s.people_linked?.length) parts.push(`faces ${s.people_linked.join(', ')}`);
    return parts.length ? parts.join('; ') : `${s.gramps_id} is in sync`;
  }

  function synced(r, prefix = '') {
    if (r.summary.errors) status = { kind: 'error', msg: prefix + syncSummary(r) };
    else succeed(prefix + syncSummary(r));
  }

  async function save() {
    if (!rec || busy || !unsaved || problem) return;
    busy = 'save';
    status = { kind: 'busy', msg: 'Saving to Immich' };
    try {
      applyRecord(await put(`/photos/api/photo/${rec.asset_id}`, payload(form)));
      succeed('Saved to Immich');
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function sync() {
    if (!rec || busy || unsaved || !syncable) return;
    busy = 'sync';
    status = { kind: 'busy', msg: 'Syncing to Gramps' };
    try {
      const r = await post(`/photos/api/photo/${rec.asset_id}/sync`, {});
      applyRecord(r.photo);
      synced(r);
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function versionAction(fn, done) {
    if (!rec || busy) return;
    busy = 'version';
    status = { kind: 'busy', msg: 'Working in Immich' };
    const old = rec.asset_id;
    try {
      applyRecord(await fn(old), old, true);
      succeed(done);
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function addVersion(candidate, mainId) {
    if (!rec || busy) return;
    busy = 'version';
    status = { kind: 'busy', msg: candidate.file ? 'Uploading to Immich' : 'Adding the version' };
    const old = rec.asset_id;
    try {
      let r;
      if (candidate.file) {
        const modified = new Date(candidate.file.lastModified || Date.now()).toISOString();
        const u = await upload(
          `/photos/api/photo/${old}/versions/upload?${qs({ filename: candidate.file.name, modified })}`,
          candidate.file,
        );
        r = u.photo;
        if (mainId === candidate.asset_id) mainId = u.asset_id;
      } else {
        r = await post(`/photos/api/photo/${old}/versions`, { asset_id: candidate.asset_id });
      }
      applyRecord(r, old, r.asset_id === old);
      if (mainId === r.asset_id) {
        succeed('Version added');
        return;
      }
      status = { kind: 'busy', msg: 'Changing the main image' };
      const p = await post(`/photos/api/photo/${r.asset_id}/versions/${mainId}/promote`, {});
      applyRecord(p.photo, r.asset_id, true);
      if (p.run_id) synced(p, 'Version added and made main; ');
      else succeed('Version added and made main');
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
      release(candidate);
    }
  }

  function release(candidate) {
    if (candidate?.file) URL.revokeObjectURL(candidate.thumb);
  }

  const matchVersion = (m) =>
    versionAction(
      (old) => post(`/photos/api/photo/${old}/versions/${m.asset_id}/match`, {}),
      'Version matched to the main image',
    );

  const removeVersion = (m) =>
    versionAction(
      (old) => del(`/photos/api/photo/${old}/versions/${m.asset_id}`),
      'Removed from the versions; its sync and ID tags were cleared',
    );

  async function promoteVersion(m) {
    if (!rec || busy) return;
    busy = 'version';
    status = { kind: 'busy', msg: rec.gramps ? 'Changing the main image and syncing' : 'Changing the main image' };
    const old = rec.asset_id;
    try {
      const r = await post(`/photos/api/photo/${old}/versions/${m.asset_id}/promote`, {});
      applyRecord(r.photo, old, true);
      if (r.run_id) synced(r, 'Main image changed; ');
      else succeed('Main image changed');
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function saveLabel(m, label) {
    if (!rec || busy) return;
    busy = 'label';
    status = { kind: 'busy', msg: 'Saving the version note' };
    try {
      applyRecord(await put(`/photos/api/photo/${rec.asset_id}/versions/${m.asset_id}/label`, { label }), null, true);
      succeed(label ? 'Version note saved' : 'Version note removed');
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function addToCollection(it) {
    if (!rec || busy) return;
    busy = 'collection';
    status = { kind: 'busy', msg: 'Adding to the collection' };
    try {
      let id = it.id;
      if (id === '__new') id = (await post('/photos/api/collections', { name: it.name, description: '' })).id;
      await post(`/photos/api/collections/${id}/items`, { asset_ids: [rec.asset_id] });
      applyRecord(await get(`/photos/api/photo/${rec.asset_id}`), null, true);
      loadCollections();
      succeed(`Added to ${it.name || it.label}`);
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  async function removeFromCollection(c) {
    if (!rec || busy) return;
    busy = 'collection';
    status = { kind: 'busy', msg: 'Removing from the collection' };
    try {
      await del(`/photos/api/collections/${c.id}/items/${rec.asset_id}`);
      applyRecord(await get(`/photos/api/photo/${rec.asset_id}`), null, true);
      loadCollections();
      succeed(`Removed from ${c.name}`);
    } catch (e) {
      fail(e);
    } finally {
      busy = '';
    }
  }

  function mainAsVersion(r) {
    const main = (r.versions?.members || []).find((m) => m.is_primary);
    return main || { asset_id: r.asset_id, filename: r.filename, width: r.width, height: r.height, label: r.label };
  }
</script>

{#snippet appLink(href, icon, title)}
  <a
    {href}
    {title}
    target="_blank"
    rel="noopener"
    class="hover:text-primary grid size-9 shrink-0 place-items-center rounded-full text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
  >
    <span class="app-icon size-6" style="--icon: url('/static/vendor/icons/{icon}.svg')"></span>
  </a>
{/snippet}

<Dialog.Root
  open
  onOpenChange={(open) => {
    if (!open) onClose();
  }}
>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 z-40 bg-black/30 dark:bg-black/70" />
    <Dialog.Content
      bind:ref={content}
      class="bg-light dark:bg-subtle fixed inset-0 z-50 flex flex-col overflow-hidden outline-none sm:inset-x-4 sm:top-22 sm:bottom-4 sm:m-auto sm:max-h-[58rem] sm:max-w-[76rem] sm:rounded-2xl sm:border sm:shadow-sm sm:dark:border-white/10"
      onOpenAutoFocus={(e) => {
        e.preventDefault();
        content?.focus();
      }}
    >
      <header class="flex shrink-0 items-center gap-1 border-b border-gray-200 px-5 py-3 dark:border-white/10">
        <Dialog.Title class="text-dark/90 min-w-0 grow truncate pe-2 text-lg font-semibold">
          {rec ? rec.title || rec.filename : 'Loading…'}
        </Dialog.Title>
        {#if rec?.immich_url}{@render appLink(rec.immich_url, 'immich', 'Open in Immich')}{/if}
        {#if rec?.gramps?.url}{@render appLink(rec.gramps.url, 'gramps-web', `Open ${rec.gramps.gramps_id} in Gramps`)}{/if}
        <CloseButton class="-me-2" onclick={onClose} />
      </header>

      <div class="flex min-h-0 flex-1 flex-col px-5 py-4">
        {#if recError}
          <Alert color="danger" title={recError} />
        {:else if !rec}
          <div class="grid flex-1 place-items-center"><LoadingSpinner size="giant" /></div>
        {:else}
          <div
            class="grid min-h-0 flex-1 grid-cols-1 gap-6 max-lg:grid-rows-[minmax(0,2fr)_minmax(0,3fr)] lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"
          >
            <button
              type="button"
              class="bg-light-100 min-h-0 cursor-zoom-in overflow-hidden rounded-xl"
              title="View larger"
              onclick={() => (lightbox = mainAsVersion(rec))}
            >
              <img src={rec.preview} alt="" class="size-full object-contain" />
            </button>
            <Tabs.Root
              value={tab}
              onValueChange={(v) => {
                tab = v;
                if (status?.kind === 'error') status = null;
              }}
              class="flex min-h-0 min-w-0 flex-col"
            >
              <Tabs.List
                class="flex shrink-0 gap-1 overflow-x-auto overflow-y-hidden shadow-[inset_0_-1px_0_var(--immich-ui-default-border)]"
              >
                {#each tabs as t (t.id)}
                  <Tabs.Trigger
                    value={t.id}
                    class="hover:text-primary data-[state=active]:border-primary data-[state=active]:text-primary focus-visible:ring-primary shrink-0 cursor-pointer rounded-t-md border-b-2 border-transparent px-3 py-2 text-sm font-medium whitespace-nowrap text-gray-600 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-inset dark:text-gray-400"
                  >
                    {t.label}
                  </Tabs.Trigger>
                {/each}
              </Tabs.List>
              <Tabs.Content value="details" class="immich-scrollbar min-h-0 flex-1 overflow-y-auto pt-4 pe-1">
                <DetailsTab {rec} bind:form />
              </Tabs.Content>
              <Tabs.Content value="versions" class="min-h-0 flex-1 pt-4">
                <VersionsTab
                  {rec}
                  {busy}
                  onAdd={(c) => (adding = c)}
                  onMatch={matchVersion}
                  onPromote={promoteVersion}
                  onRemove={removeVersion}
                  onLabel={saveLabel}
                  onView={(m) => (lightbox = m)}
                  onError={(msg) => (status = { kind: 'error', msg })}
                />
              </Tabs.Content>
              <Tabs.Content value="people" class="immich-scrollbar min-h-0 flex-1 overflow-y-auto pt-4">
                {#if rec.people.length}
                  <ul class="flex flex-col">
                    {#each rec.people as p (p.id)}
                      <li class="border-b py-2 last:border-b-0 dark:border-white/10">
                        <p class="text-sm">{p.name || '(unnamed)'}</p>
                        {#if !p.linked}
                          <p class="text-xs text-gray-600 dark:text-gray-400">Not linked to a Gramps person yet</p>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {:else}
                  <Text size="small" color="muted">No faces.</Text>
                {/if}
              </Tabs.Content>
              <Tabs.Content value="collections" class="immich-scrollbar min-h-0 flex-1 overflow-y-auto pt-4">
                <CollectionsTab {rec} {busy} onAdd={addToCollection} onRemove={removeFromCollection} onGo={onClose} />
              </Tabs.Content>
            </Tabs.Root>
          </div>
        {/if}
      </div>

      {#if rec}
        <footer class="flex shrink-0 items-center gap-2 border-t border-gray-200 px-5 py-3 dark:border-white/10">
          <div class="flex min-w-0 grow items-center gap-2 text-sm">
            {#if status?.kind === 'busy'}
              <LoadingSpinner size="small" />
              <span class="truncate text-gray-600 dark:text-gray-400">{status.msg}</span>
            {:else if status?.kind === 'error'}
              <Text size="small" color="danger" class="line-clamp-2">{status.msg}</Text>
            {:else if edited}
              <span class="text-gray-600 dark:text-gray-400">Unsaved changes</span>
            {/if}
          </div>
          <Button
            variant="outline"
            color="secondary"
            leadingIcon={mdiContentSaveOutline}
            disabled={!unsaved || !!problem || !!busy}
            onclick={save}
          >
            Save
          </Button>
          <Button leadingIcon={mdiSync} disabled={unsaved || !syncable || !!busy} onclick={sync}>Sync to Gramps</Button>
        </footer>
      {/if}
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>

<Lightbox item={lightbox} onClose={() => (lightbox = null)} />

{#if adding && rec}
  <AddVersionDialog
    {rec}
    candidate={adding}
    unsaved={edited}
    onClose={() => {
      release(adding);
      adding = null;
    }}
    onConfirm={(mainId) => {
      const c = adding;
      adding = null;
      addVersion(c, mainId);
    }}
  />
{/if}
