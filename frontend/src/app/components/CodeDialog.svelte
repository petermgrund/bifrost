<script>
  import { Button, Input, Text, toastManager } from '@immich/ui';
  import { mdiCallMerge, mdiFileDocumentOutline, mdiMagnify, mdiTrashCanOutline } from '@mdi/js';
  import { RadioGroup } from 'bits-ui';
  import { del, post } from '../lib/api.svelte.js';
  import { mediaMatches } from '../lib/format.js';
  import { loadMedia, store } from '../lib/store.svelte.js';
  import AppLink from './AppLink.svelte';
  import MediaThumb from './MediaThumb.svelte';
  import Modal from './Modal.svelte';

  let { item, onClose } = $props();

  let view = $state('details');
  let q = $state('');
  let other = $state(null);
  let keep = $state('');
  let busy = $state(false);
  let error = $state('');

  const needle = $derived(q.trim().toLowerCase());
  const others = $derived((store.media || []).filter((m) => m.code !== item.code && mediaMatches(m, needle)));
  const pair = $derived(other ? [item, other] : []);

  function show(next) {
    view = next;
    error = '';
    other = null;
    keep = '';
    q = '';
  }

  async function change(run, done) {
    if (busy) return;
    busy = true;
    error = '';
    try {
      const r = await run();
      const problems = r.problems || [];
      if (problems.length) toastManager.warning([done(r), ...problems].join(' '));
      else toastManager.primary(done(r));
      await loadMedia();
      onClose();
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  const remove = () => change(() => del(`/media/api/${encodeURIComponent(item.code)}`), (r) => `${r.code} deleted`);

  function merge() {
    const gone = pair.find((m) => m.code !== keep);
    if (!keep || !gone) return;
    change(
      () => post(`/media/api/${encodeURIComponent(gone.code)}/merge`, { into: keep }),
      (r) => `${r.code} merged into ${r.into}`,
    );
  }
</script>

{#snippet summary(m)}
  <MediaThumb item={m} />
  <span class="min-w-0 flex-1">
    <span class="block truncate text-sm font-medium">{m.title || 'No title'}</span>
    <span class="block truncate font-mono text-xs text-gray-600 dark:text-gray-400">{m.code}</span>
  </span>
{/snippet}

<Modal {onClose}>
  {#snippet heading()}
    <span class="font-mono">{item.code}</span>
    {#if view === 'merge'}<span class="text-base font-normal text-gray-500 dark:text-gray-400">Merge</span>{/if}
    {#if view === 'delete'}<span class="text-base font-normal text-gray-500 dark:text-gray-400">Delete</span>{/if}
  {/snippet}

  <div class="flex flex-col gap-4 px-5 py-4">
    {#if view !== 'merge'}
      <div class="flex items-start gap-4">
        <MediaThumb {item} class="size-24" />
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium break-words">{item.title || 'No title'}</p>
          {#if item.attention}<Text size="small" color="danger">{item.attention}</Text>{/if}
          {#if item.merged.length}
            <p class="mt-1 text-xs text-gray-600 dark:text-gray-400">
              Merged <span class="font-mono">{item.merged.join(', ')}</span>
            </p>
          {/if}
          <div class="-ms-2 mt-1 flex items-center">
            {#if item.gramps_url}<AppLink href={item.gramps_url} app="gramps-web" title="Open {item.code} in Gramps" />{/if}
            {#each item.immich as a (a.id)}
              {#if a.url}<AppLink href={a.url} app="immich" title="Open in Immich" />{/if}
            {/each}
            {#each item.paperless as d (d.id)}
              {#if d.url}<AppLink href={d.url} icon={mdiFileDocumentOutline} title="Open document {d.id} in Paperless" />{/if}
            {/each}
          </div>
        </div>
      </div>
    {:else if !other}
      <div {@attach (node) => node.querySelector('input')?.focus()}>
        <Input
          bind:value={q}
          size="small"
          shape="round"
          leadingIcon={mdiMagnify}
          placeholder="Search"
          aria-label="Search for the other one"
        />
      </div>
      <ul class="flex max-h-80 flex-col overflow-y-auto">
        {#each others.slice(0, 50) as m (m.code)}
          <li>
            <button
              type="button"
              class="ring-primary flex w-full cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 text-start outline-none hover:bg-gray-100 focus-visible:ring-2 dark:hover:bg-white/5"
              onclick={() => (other = m)}
            >
              {@render summary(m)}
            </button>
          </li>
        {/each}
      </ul>
      {#if !others.length}<Text size="small" color="muted">Nothing matches</Text>{/if}
    {:else}
      <Text size="small" fontWeight="medium">Keep</Text>
      <RadioGroup.Root value={keep} onValueChange={(v) => v && (keep = v)} aria-label="Keep" class="flex flex-col gap-2">
        {#each pair as m (m.code)}
          <RadioGroup.Item
            value={m.code}
            class="data-[state=checked]:border-primary data-[state=checked]:bg-primary/5 focus-visible:ring-primary flex w-full cursor-pointer items-center gap-3 rounded-xl border border-gray-200 px-3 py-2 text-start transition-colors outline-none hover:bg-gray-50 focus-visible:ring-2 dark:border-white/10 dark:hover:bg-white/5"
          >
            {#snippet children({ checked })}
              {@render summary(m)}
              <span
                class={[
                  'grid size-5 shrink-0 place-items-center rounded-full border-2',
                  checked ? 'border-primary' : 'border-gray-300 dark:border-gray-600',
                ]}
              >
                {#if checked}<span class="bg-primary size-2.5 rounded-full"></span>{/if}
              </span>
            {/snippet}
          </RadioGroup.Item>
        {/each}
      </RadioGroup.Root>
    {/if}
    {#if error}<Text size="small" color="danger">{error}</Text>{/if}
  </div>

  {#snippet footer()}
    {#if view === 'details'}
      <Button variant="outline" color="secondary" leadingIcon={mdiCallMerge} onclick={() => show('merge')}>Merge</Button>
      <Button variant="outline" color="danger" leadingIcon={mdiTrashCanOutline} onclick={() => show('delete')}>Delete</Button>
    {:else if view === 'delete'}
      <Button variant="outline" color="secondary" disabled={busy} onclick={() => show('details')}>Cancel</Button>
      <Button color="danger" leadingIcon={mdiTrashCanOutline} disabled={busy} onclick={remove}>Delete {item.code}</Button>
    {:else}
      <Button variant="outline" color="secondary" disabled={busy} onclick={() => (other ? show('merge') : show('details'))}>
        {other ? 'Back' : 'Cancel'}
      </Button>
      {#if other}
        <Button color="danger" leadingIcon={mdiCallMerge} disabled={busy || !keep} onclick={merge}>
          {keep ? `Keep ${keep}` : 'Merge'}
        </Button>
      {/if}
    {/if}
  {/snippet}
</Modal>
