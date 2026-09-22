<script>
  import { Button, Checkbox, Field, Input, Label, Select, Text, Textarea } from '@immich/ui';
  import { mdiClose, mdiMapMarkerOff, mdiMapMarkerPlusOutline } from '@mdi/js';
  import { MODIFIER, MONTH_OPTIONS, QUALITY, dateOf, dateParts, dateProblem, grampsDate, placeItem } from '../lib/format.js';
  import { store } from '../lib/store.svelte.js';
  import PickerPopover from './PickerPopover.svelte';
  import Segmented from './Segmented.svelte';

  let { rec, form = $bindable() } = $props();

  let placeQ = $state('');

  const problem = $derived(dateProblem(form.date));
  const date = $derived(dateOf(form.date));
  const immichDate = $derived(rec.tagged_date ? grampsDate(rec.tagged_date) : rec.immich_date);
  const inGramps = $derived(!!rec.gramps);
  const off = $derived(!inGramps && !form.sync.media);
  const syncBoxes = $derived([
    { key: 'title', label: 'Title', disabled: off },
    { key: 'date', label: 'Date', disabled: off || !date },
    { key: 'note', label: 'Note', disabled: off },
  ]);

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
  }

  function setMonth(value) {
    form.date.month = value;
    if (value === '0') form.date.day = '';
  }

  function useImmichDate() {
    if (rec.tagged_date) {
      form.date = dateParts(rec.tagged_date);
      return;
    }
    const [year, month, day] = rec.immich_date.split('-');
    form.date.year = year;
    form.date.month = String(+month);
    form.date.day = form.date.modifier === 'about' ? '' : String(+day);
  }

  function clearDate() {
    form.date.year = '';
    form.date.month = '0';
    form.date.day = '';
  }
</script>

<div class="flex flex-col gap-2">
  <Field label="Title">
    <Input bind:value={form.title} />
  </Field>

  <div class="@container flex flex-col gap-1.5">
    <Label label="Date" size="small" />
    <Segmented label="Date type" options={MODIFIER} value={form.date.modifier} onChange={setModifier} />
    <div
      class="grid grid-cols-[4.5rem_minmax(0,1fr)_3.5rem] gap-2 @sm:grid-cols-[4.5rem_minmax(0,1.2fr)_3.5rem_minmax(0,1fr)]"
    >
      <Field label="Year" invalid={!!problem && !/^\d{4}$/.test(form.date.year.trim())}>
        <Input bind:value={form.date.year} inputmode="numeric" maxlength={4} placeholder="YYYY" class="font-mono" />
      </Field>
      <Field label="Month">
        <Select options={MONTH_OPTIONS} value={form.date.month} onChange={setMonth} />
      </Field>
      <Field
        label="Day"
        disabled={form.date.month === '0' || form.date.modifier === 'about'}
        invalid={!!problem && !!form.date.day.trim()}
      >
        <Input bind:value={form.date.day} inputmode="numeric" maxlength={2} placeholder="DD" class="font-mono" />
      </Field>
      <Field label="Quality" class="col-span-3 @sm:col-span-1">
        <Select options={QUALITY} value={form.date.quality} onChange={(v) => (form.date.quality = v)} />
      </Field>
    </div>
    {#if problem}
      <Text size="small" color="danger">{problem}</Text>
    {:else if date}
      <div class="flex items-center justify-between gap-2">
        <span class="text-dark font-mono text-sm font-bold">{grampsDate(date)}</span>
        <Button size="small" variant="ghost" color="secondary" leadingIcon={mdiClose} onclick={clearDate}>
          Clear date
        </Button>
      </div>
    {:else if immichDate && !form.date.year}
      <button type="button" class="text-primary w-fit text-sm font-medium hover:underline" onclick={useImmichDate}>
        Use Immich's {immichDate}
      </button>
    {/if}
  </div>

  <div class="flex flex-col items-start gap-1">
    <Label label="Place" size="small" />
    <PickerPopover
      label={form.place ? form.place.label : 'Choose place'}
      icon={form.place ? form.place.icon : mdiMapMarkerPlusOutline}
      items={placeItems}
      bind:query={placeQ}
      placeholder="Search Gramps places"
      empty={!placeQ.trim() ? '' : store.places ? 'No Gramps place matches' : 'Loading places…'}
      onPick={(it) => (form.place = it.id === '__none' ? null : it)}
    />
  </div>

  <Field label="Notes">
    <Textarea bind:value={form.notes} rows={1} grow />
  </Field>

  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
    <Text size="small" color="muted">Sync to Gramps</Text>
    {#if !inGramps}
      <label class="flex cursor-pointer items-center gap-2 text-sm">
        <Checkbox size="tiny" checked={form.sync.media} onCheckedChange={(v) => (form.sync.media = v)} />
        Media object
      </label>
    {/if}
    {#each syncBoxes as box (box.key)}
      <label class={['flex items-center gap-2 text-sm', box.disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer']}>
        <Checkbox
          size="tiny"
          checked={form.sync[box.key] && !box.disabled}
          disabled={box.disabled}
          onCheckedChange={(v) => (form.sync[box.key] = v)}
        />
        {box.label}
      </label>
    {/each}
  </div>
</div>
