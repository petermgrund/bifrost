<script>
  import { Badge, Button, Field, IconButton, Input, Label, Link, Select, Text, Textarea } from '@immich/ui';
  import { mdiClose, mdiLinkPlus, mdiMapMarkerOff, mdiMapMarkerPlusOutline } from '@mdi/js';
  import {
    LINK_RE,
    MODIFIER,
    MONTH_OPTIONS,
    QUALITY,
    RANGES,
    dateOf,
    dateProblem,
    grampsDate,
    placeItem,
    shortLink,
  } from '../lib/format.js';
  import { store } from '../lib/store.svelte.js';
  import PickerPopover from './PickerPopover.svelte';
  import Segmented from './Segmented.svelte';

  let { rec, form = $bindable(), busy, onError } = $props();

  let placeQ = $state('');
  let url = $state('');

  const problem = $derived(dateProblem(form.date));
  const date = $derived(dateOf(form.date));
  const heldDate = $derived(!!rec.date_readonly && !form.date.replace);
  const manyPlaces = $derived((rec.places || []).length > 1);

  const placeItems = $derived.by(() => {
    const q = placeQ.trim().toLowerCase();
    if (!q) return form.place ? [{ id: '__none', label: 'No place', icon: mdiMapMarkerOff }] : [];
    const rank = (p) => {
      const name = p.name.toLowerCase();
      let r = -1;
      if (name.startsWith(q)) r = 0;
      else if (name.includes(q) || p.gramps_id.toLowerCase().includes(q)) r = 1;
      else if (p.hierarchy.join(', ').toLowerCase().includes(q)) r = 2;
      return r < 0 ? r : r + (p.tagged ? 0 : 3);
    };
    return (store.places || [])
      .map((p) => ({ p, r: rank(p) }))
      .filter((x) => x.r >= 0)
      .sort((a, b) => a.r - b.r)
      .slice(0, 6)
      .map(({ p }) => placeItem(p));
  });

  function setModifier(value) {
    form.date.modifier = value;
    if (value === 'about') form.date.day = '';
    if (RANGES.includes(value)) {
      form.date.month = '0';
      form.date.day = '';
    }
  }

  function setMonth(value) {
    form.date.month = value;
    if (value === '0') form.date.day = '';
  }

  function clearDate() {
    form.date.year = '';
    form.date.month = '0';
    form.date.day = '';
  }

  function addLink(e) {
    e.preventDefault();
    const value = url.trim();
    if (!value || busy) return;
    if (!LINK_RE.test(value)) {
      onError('That is not a link starting with http:// or https://.');
      return;
    }
    if (form.links.includes(value)) {
      onError('This photo already has that link.');
      return;
    }
    form.links = [...form.links, value];
    url = '';
  }

  function removeLink(value) {
    form.links = form.links.filter((l) => l !== value);
  }
</script>

<div class="flex flex-col gap-2">
  <Field label="Title">
    <Input bind:value={form.title} />
  </Field>

  <div class="@container flex flex-col gap-1.5">
    <Label label="Date" size="small" />
    {#if heldDate}
      <div class="flex flex-wrap items-center gap-2">
        <Badge color="secondary" shape="round" size="small" class="font-mono font-normal">{rec.date_readonly}</Badge>
        {#if rec.gramps?.url}
          <Link href={rec.gramps.url} target="_blank" rel="noopener" class="text-sm">Edit in Gramps Web</Link>
        {/if}
        <Button size="tiny" variant="ghost" color="secondary" onclick={() => (form.date.replace = true)}>Replace</Button>
      </div>
    {:else}
      <Segmented label="Date type" options={MODIFIER} value={form.date.modifier} onChange={setModifier} />
      <div
        class={[
          'grid gap-2',
          form.date.modifier === 'span'
            ? 'grid-cols-[4.5rem_4.5rem_4.5rem] @sm:grid-cols-[4.5rem_4.5rem_4.5rem_minmax(0,1fr)]'
            : 'grid-cols-[4.5rem_minmax(0,1fr)_3.5rem] @sm:grid-cols-[4.5rem_minmax(0,1.2fr)_3.5rem_minmax(0,1fr)]',
        ]}
      >
        <Field label="Year" invalid={!!problem && !/^\d{4}$/.test(form.date.year.trim())}>
          <Input bind:value={form.date.year} inputmode="numeric" maxlength={4} placeholder="YYYY" class="font-mono" />
        </Field>
        {#if form.date.modifier === 'span'}
          <Field label="− years" invalid={!!problem && !/^\d{0,3}$/.test(form.date.minus.trim())}>
            <Input bind:value={form.date.minus} inputmode="numeric" maxlength={3} placeholder="0" class="font-mono" />
          </Field>
          <Field label="+ years" invalid={!!problem && !/^\d{0,3}$/.test(form.date.plus.trim())}>
            <Input bind:value={form.date.plus} inputmode="numeric" maxlength={3} placeholder="0" class="font-mono" />
          </Field>
        {:else}
          <Field label="Month" disabled={form.date.modifier === 'decade'}>
            <Select options={MONTH_OPTIONS} value={form.date.month} onChange={setMonth} />
          </Field>
          <Field
            label="Day"
            disabled={form.date.month === '0' || form.date.modifier === 'about' || form.date.modifier === 'decade'}
            invalid={!!problem && !!form.date.day.trim()}
          >
            <Input bind:value={form.date.day} inputmode="numeric" maxlength={2} placeholder="DD" class="font-mono" />
          </Field>
        {/if}
        <Field label="Quality" class="col-span-3 @sm:col-span-1">
          <Select options={QUALITY} value={form.date.quality} onChange={(v) => (form.date.quality = v)} />
        </Field>
      </div>
      {#if problem}
        <Text size="small" color="danger">{problem}</Text>
      {:else if date}
        <Badge
          color="primary"
          shape="round"
          size="small"
          class="self-start font-mono font-normal"
          translations={{ close: 'Clear date' }}
          onClose={clearDate}
        >
          {grampsDate(date)}
        </Badge>
      {/if}
    {/if}
  </div>

  <div class="flex flex-col items-start gap-1">
    <Label label="Place" size="small" />
    {#if manyPlaces}
      <div class="flex flex-wrap items-center gap-2">
        {#each rec.places as p (p.gramps_id)}
          <Badge color="secondary" shape="round" size="small">{p.name}</Badge>
        {/each}
        {#if rec.gramps?.url}
          <Link href={rec.gramps.url} target="_blank" rel="noopener" class="text-sm">Edit in Gramps Web</Link>
        {/if}
      </div>
    {:else}
      <PickerPopover
        label={form.place ? form.place.label : 'Choose place'}
        icon={form.place ? form.place.icon : mdiMapMarkerPlusOutline}
        items={placeItems}
        bind:query={placeQ}
        placeholder="Search Gramps places"
        empty={!placeQ.trim() ? '' : store.places ? 'No Gramps place matches' : 'Loading places…'}
        onPick={(it) => (form.place = it.id === '__none' ? null : it)}
      />
    {/if}
  </div>

  <Field label="Notes">
    <Textarea bind:value={form.notes} rows={1} grow />
  </Field>

  <div class="flex flex-col gap-1.5">
    <Label label="Links" size="small" />
    {#if form.links.length}
      <ul class="flex flex-col gap-0.5">
        {#each form.links as l (l)}
          <li class="flex items-center gap-1">
            <Link href={l} title={l} class="text-sm">{shortLink(l)}</Link>
            <IconButton
              icon={mdiClose}
              size="tiny"
              shape="round"
              variant="ghost"
              color="secondary"
              aria-label="Remove {l}"
              disabled={!!busy}
              onclick={() => removeLink(l)}
            />
          </li>
        {/each}
      </ul>
    {/if}
    <form class="flex items-center gap-2" onsubmit={addLink}>
      <div class="min-w-0 grow">
        <Input bind:value={url} placeholder="https://" aria-label="Link" disabled={!!busy} />
      </div>
      <Button type="submit" variant="outline" color="secondary" leadingIcon={mdiLinkPlus} disabled={!url.trim() || !!busy}>
        Add
      </Button>
    </form>
  </div>
</div>
