<script>
  import { Alert, Button, Field, Heading, Icon, Input, LoadingSpinner, Text, toastManager } from '@immich/ui';
  import {
    mdiAccountOutline,
    mdiAccountSearchOutline,
    mdiChevronDown,
    mdiFaceRecognition,
    mdiLinkPlus,
    mdiLinkVariant,
    mdiLinkVariantOff,
    mdiMagnify,
    mdiRefresh,
  } from '@mdi/js';
  import { SvelteSet } from 'svelte/reactivity';
  import { del, get, post } from '../lib/api.svelte.js';
  import PickerPopover from './PickerPopover.svelte';
  import Segmented from './Segmented.svelte';

  const RINGS = ['ring-3 ring-primary', 'ring-3 ring-[#9a4523] dark:ring-[#ffb59a]'];
  const thumb = (id) => `/faces/api/person-thumbnail/${id}`;

  let links = $state(null);
  let grampsUrl = $state('');
  let accounts = $state([]);
  let gPeople = $state([]);
  let iPeople = $state([]);
  let loadError = $state('');
  let busy = $state('');
  let query = $state('');
  let filter = $state('all');
  let open = $state(null);
  let labelDraft = $state('');
  let selI = $state(null);
  let selG = $state(null);
  let qI = $state('');
  let qG = $state('');
  let label = $state('');
  let form = $state(null);
  const unloaded = new SvelteSet();

  const people = $derived(new Map(gPeople.map((p) => [p.handle, p])));
  const named = $derived(iPeople.filter((p) => !p.is_hidden && p.name.trim()));
  const linkedIds = $derived(new Set((links || []).flatMap((g) => g.links.map((l) => l.immich_person_id))));
  const backlog = $derived(named.filter((p) => !linkedIds.has(p.id)));
  const broken = $derived((links || []).filter((g) => g.links.some((l) => !l.resolved)));
  const sorted = $derived(
    [...(links || [])].sort((a, b) => nameOf(a).localeCompare(nameOf(b), undefined, { sensitivity: 'base' })),
  );
  const needle = $derived(query.trim().toLowerCase());
  const groups = $derived((filter === 'broken' ? broken : sorted).filter((g) => !needle || matches(g)));
  const unlinked = $derived(backlog.filter((p) => !needle || p.name.toLowerCase().includes(needle)));

  const immichItems = $derived.by(() => {
    const q = qI.trim().toLowerCase();
    return [...backlog, ...named.filter((p) => linkedIds.has(p.id))]
      .filter((p) => !q || p.name.toLowerCase().includes(q))
      .slice(0, 8)
      .map(immichItem);
  });

  const grampsItems = $derived.by(() => {
    const q = qG.trim().toLowerCase();
    return gPeople
      .filter((p) => !q || p.name.toLowerCase().includes(q) || p.gramps_id.toLowerCase().includes(q))
      .slice(0, 8)
      .map((p) => ({ id: p.handle, label: p.name, sub: p.gramps_id, icon: mdiAccountOutline }));
  });

  load();

  function immichItem(p) {
    return { id: p.id, label: p.name, sub: p.account_label, thumb: thumb(p.id), round: true };
  }

  function nameOf(g) {
    return people.get(g.gramps_handle)?.name || g.gramps_handle;
  }

  function matches(g) {
    const p = people.get(g.gramps_handle);
    return [nameOf(g), p?.gramps_id || '', g.label || '', ...g.links.map((l) => l.person_name || '')]
      .join(' ')
      .toLowerCase()
      .includes(needle);
  }

  function letters(list) {
    const out = [];
    for (const g of list) {
      const letter = (nameOf(g)[0] || '?').toUpperCase();
      const last = out[out.length - 1];
      if (last && last.letter === letter) last.groups.push(g);
      else out.push({ letter, groups: [g] });
    }
    return out;
  }

  function ringOf(account) {
    const i = accounts.indexOf(account);
    return RINGS[i < 0 ? accounts.length : i] || 'ring-0';
  }

  function ordered(g) {
    const at = (l) => (accounts.includes(l.account_label) ? accounts.indexOf(l.account_label) : accounts.length);
    return [...g.links].sort((a, b) => at(a) - at(b));
  }

  const storedLabel = (g) => g.links.map((l) => l.label).find(Boolean) || '';
  const who = (l) => (l.resolved ? `${l.person_name || '(unnamed)'} (${l.account_label})` : 'deleted Immich person');

  function applyLinks(r) {
    links = r.faces;
    grampsUrl = r.gramps_url || '';
    accounts = r.accounts || accounts;
  }

  async function load(refresh = false) {
    busy = 'load';
    const fresh = refresh ? '?refresh=1' : '';
    try {
      const [l, g, i] = await Promise.all([
        get('/faces/api/links'),
        get(`/faces/api/gramps-people${fresh}`),
        get(`/faces/api/immich-people${fresh}`),
      ]);
      applyLinks(l);
      gPeople = g;
      iPeople = i;
      loadError = '';
    } catch (e) {
      if (links === null) loadError = e.message;
      else toastManager.danger(e.message);
    } finally {
      busy = '';
    }
  }

  function refresh() {
    query = '';
    filter = 'all';
    open = null;
    unloaded.clear();
    load(true);
  }

  function toggle(g) {
    open = open === g.gramps_handle ? null : g.gramps_handle;
    if (open) labelDraft = storedLabel(g);
  }

  async function addLink() {
    if (!selI || !selG || busy) return;
    busy = 'link';
    try {
      applyLinks(
        await post('/faces/api/links', { gramps_handle: selG.id, immich_person_id: selI.id, label: label.trim() }),
      );
      toastManager.primary(`Linked ${selI.label} to ${selG.label}`);
      selI = null;
      selG = null;
      label = '';
    } catch (e) {
      toastManager.danger(e.message);
    } finally {
      busy = '';
    }
  }

  async function saveLabel(g) {
    const targets = ordered(g).filter((l) => l.resolved);
    if (!targets.length || busy) return;
    busy = 'link';
    try {
      let r = null;
      for (const l of targets) {
        r = await post('/faces/api/links', {
          gramps_handle: g.gramps_handle,
          immich_person_id: l.immich_person_id,
          label: labelDraft.trim(),
        });
      }
      applyLinks(r);
    } catch (e) {
      toastManager.danger(e.message);
    } finally {
      busy = '';
    }
  }

  async function removeLink(g) {
    busy = 'link';
    try {
      applyLinks(await del(`/faces/api/links/${g.gramps_handle}`));
      open = null;
    } catch (e) {
      toastManager.danger(e.message);
    } finally {
      busy = '';
    }
  }

  function linkFrom(p) {
    selI = immichItem(p);
    form?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
</script>

{#snippet face(id, account, title)}
  {#if unloaded.has(id)}
    <span
      class={['grid size-11 shrink-0 place-items-center rounded-full bg-gray-100 text-gray-500 dark:bg-gray-800', ringOf(account)]}
      {title}
    >
      <Icon icon={mdiAccountOutline} size="1.5rem" />
    </span>
  {:else}
    <img
      src={thumb(id)}
      alt=""
      loading="lazy"
      {title}
      class={['size-11 shrink-0 rounded-full bg-gray-100 object-cover dark:bg-gray-800', ringOf(account)]}
      onerror={() => unloaded.add(id)}
    />
  {/if}
{/snippet}

{#snippet nothingHere(text)}
  <div class="flex flex-col items-center gap-3 py-24 text-gray-500">
    <Icon icon={mdiAccountSearchOutline} size="3rem" />
    <Text>{text}</Text>
  </div>
{/snippet}

{#snippet card(g)}
  {@const ls = ordered(g)}
  {@const live = ls.filter((l) => l.resolved)}
  {@const p = people.get(g.gramps_handle)}
  {@const isOpen = open === g.gramps_handle}
  <div
    class={[
      'rounded-xl border transition-colors',
      isOpen
        ? 'border-primary bg-primary/5'
        : 'border-gray-200 hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/5',
    ]}
  >
    <button
      type="button"
      class="flex w-full cursor-pointer items-center gap-3 p-3 text-start"
      aria-expanded={isOpen}
      onclick={() => toggle(g)}
    >
      <span class="flex shrink-0 gap-2.5 p-0.5">
        {#each live.length ? live : ls.slice(0, 1) as l (l.immich_person_id)}
          {@render face(l.immich_person_id, l.account_label, who(l))}
        {/each}
      </span>
      <span class="min-w-0 flex-1">
        <span class="block font-medium break-words">{nameOf(g)}</span>
        <span class="block font-mono text-xs text-gray-600 dark:text-gray-400">{p?.gramps_id || ''}</span>
      </span>
      <Icon
        icon={mdiChevronDown}
        size="1.25rem"
        class="shrink-0 text-gray-500 transition-transform {isOpen ? 'rotate-180' : ''}"
      />
    </button>
    {#if isOpen}
      <div class="flex flex-col gap-3 border-t border-gray-200 p-3 dark:border-white/10">
        {#if live.length < ls.length}
          <Text size="small" color="danger">a link points at a deleted Immich person</Text>
        {/if}
        <div class="flex items-end gap-2">
          <Field label="Label" class="min-w-0 flex-1">
            <Input bind:value={labelDraft} onkeydown={(e) => e.key === 'Enter' && saveLabel(g)} />
          </Field>
          <Button
            size="small"
            variant="outline"
            color="secondary"
            disabled={busy !== '' || !live.length || labelDraft.trim() === storedLabel(g)}
            onclick={() => saveLabel(g)}>Save</Button
          >
        </div>
        <div class="flex items-center gap-2">
          {#if grampsUrl && p}
            <a
              href="{grampsUrl}/person/{p.gramps_id}"
              title="Open in Gramps"
              target="_blank"
              rel="noopener"
              class="hover:text-primary grid size-9 shrink-0 place-items-center rounded-full text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              <span class="app-icon size-6" style="--icon: url('/static/vendor/icons/gramps-web.svg')"></span>
            </a>
          {/if}
          <Button
            size="small"
            variant="ghost"
            color="danger"
            leadingIcon={mdiLinkVariantOff}
            class="ms-auto"
            disabled={busy !== ''}
            onclick={() => removeLink(g)}>{ls.length > 1 ? 'Remove both links' : 'Remove link'}</Button
          >
        </div>
      </div>
    {/if}
  </div>
{/snippet}

<div class="flex flex-col gap-6 p-4 md:p-6">
  <div class="flex flex-wrap items-center gap-3">
    <Heading size="medium" tag="h1" class="me-auto">Faces</Heading>
    <Button
      size="small"
      variant="outline"
      color="secondary"
      leadingIcon={mdiRefresh}
      disabled={busy !== ''}
      onclick={refresh}>Refresh</Button
    >
  </div>

  {#if links === null}
    {#if loadError}
      <Alert color="danger" title={loadError} />
    {:else}
      <div class="flex justify-center py-24"><LoadingSpinner size="large" /></div>
    {/if}
  {:else}
    <div
      bind:this={form}
      class="flex flex-wrap items-center gap-2 rounded-xl border border-gray-200 p-3 dark:border-white/10"
    >
      <PickerPopover
        label={selI?.label || 'Immich person'}
        icon={mdiFaceRecognition}
        items={immichItems}
        bind:query={qI}
        placeholder="Search Immich people"
        empty="No named Immich person matches"
        variant={selI ? 'filled' : 'outline'}
        color={selI ? 'primary' : 'secondary'}
        disabled={busy === 'link'}
        onPick={(it) => (selI = it)}
      />
      <Icon icon={mdiLinkVariant} size="1.25rem" class="text-gray-400" />
      <PickerPopover
        label={selG?.label || 'Gramps person'}
        icon={mdiAccountOutline}
        items={grampsItems}
        bind:query={qG}
        placeholder="Search name or Gramps ID"
        empty="No Gramps person matches"
        variant={selG ? 'filled' : 'outline'}
        color={selG ? 'primary' : 'secondary'}
        disabled={busy === 'link'}
        onPick={(it) => (selG = it)}
      />
      <div class="w-44">
        <Input
          bind:value={label}
          placeholder="Label (optional)"
          aria-label="Label"
          onkeydown={(e) => e.key === 'Enter' && addLink()}
        />
      </div>
      <Button size="small" loading={busy === 'link'} disabled={!selI || !selG || busy !== ''} onclick={addLink}>
        Link
      </Button>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <Segmented
        label="Show"
        value={filter}
        options={[
          { value: 'all', label: 'All linked', count: links.length },
          { value: 'unlinked', label: 'Unlinked in Immich', count: backlog.length },
          { value: 'broken', label: 'Broken links', count: broken.length },
        ]}
        onChange={(v) => {
          filter = v;
          open = null;
        }}
      />
      <div class="min-w-48 flex-1 sm:ms-auto sm:max-w-xs">
        <Input
          bind:value={query}
          shape="round"
          leadingIcon={mdiMagnify}
          placeholder="Search name, label or Gramps ID"
          aria-label="Search name, label or Gramps ID"
          oninput={() => (open = null)}
        />
      </div>
    </div>

    {#if filter === 'unlinked'}
      {#if unlinked.length}
        <div class="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {#each unlinked as p (p.id)}
            <button
              type="button"
              class="flex w-full cursor-pointer items-center gap-3 rounded-xl border border-gray-200 p-3 text-start transition-colors hover:bg-gray-50 dark:border-white/10 dark:hover:bg-white/5"
              onclick={() => linkFrom(p)}
            >
              <span class="shrink-0 p-0.5">{@render face(p.id, p.account_label, `${p.name} (${p.account_label})`)}</span>
              <span class="min-w-0 flex-1">
                <span class="block font-medium break-words">{p.name}</span>
                <span class="block text-xs text-gray-600 dark:text-gray-400">{p.account_label}</span>
              </span>
              <Icon icon={mdiLinkPlus} size="1.25rem" class="shrink-0 text-gray-500" />
            </button>
          {/each}
        </div>
      {:else}
        {@render nothingHere(needle ? `No people match “${query.trim()}”` : 'Every named Immich person is linked')}
      {/if}
    {:else if groups.length}
      {#each letters(groups) as b (b.letter)}
        <div class="flex flex-col gap-2">
          <div class="flex items-center gap-2">
            <span class="w-4 font-mono text-xs text-gray-500">{b.letter}</span>
            <span class="h-px flex-1 bg-gray-200 dark:bg-white/10"></span>
          </div>
          <div class="grid grid-cols-1 items-start gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {#each b.groups as g (g.gramps_handle)}
              {@render card(g)}
            {/each}
          </div>
        </div>
      {/each}
    {:else}
      {@render nothingHere(
        needle ? `No people match “${query.trim()}”` : filter === 'broken' ? 'No broken links' : 'No links yet',
      )}
    {/if}
  {/if}
</div>
