<script>
  import { Button, CloseButton, Icon, Text } from '@immich/ui';
  import { mdiImageOutline } from '@mdi/js';
  import { Dialog, RadioGroup } from 'bits-ui';
  import { untrack } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import { sizeText } from '../lib/format.js';

  let { rec, candidate, unsaved = false, onConfirm, onClose } = $props();

  const takesOver = $derived(!rec.gramps && !!candidate.gramps_id);
  const candidateName = $derived(candidate.title || candidate.filename);

  const options = $derived.by(() => {
    const current = rec.versions?.members?.length
      ? rec.versions.members
      : [{ asset_id: rec.asset_id, filename: rec.filename, thumb: rec.thumb, is_primary: true }];
    return [
      ...current.map((m) => ({
        id: m.asset_id,
        name: m.filename,
        thumb: m.thumb,
        tags: [m.is_primary && 'Main now', m.is_primary && rec.gramps && `in Gramps as ${rec.gramps.gramps_id}`],
      })),
      {
        id: candidate.asset_id,
        name: candidate.filename || candidate.title,
        thumb: candidate.thumb,
        tags: candidate.file
          ? ['Upload', sizeText(candidate)]
          : ['New', candidate.gramps_id && `in Gramps as ${candidate.gramps_id}`],
      },
    ];
  });

  let main = $state(untrack(() => (!rec.gramps && candidate.gramps_id ? candidate.asset_id : rec.asset_id)));
  const broken = new SvelteSet();
</script>

<Dialog.Root
  open
  onOpenChange={(open) => {
    if (!open) onClose();
  }}
>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 z-60 bg-black/30 dark:bg-black/70" />
    <Dialog.Content
      class="bg-light dark:bg-subtle fixed inset-0 z-60 m-auto flex h-fit max-h-[90dvh] w-[min(34rem,calc(100vw-2rem))] flex-col overflow-hidden rounded-2xl border shadow-sm outline-none dark:border-white/10"
      onOpenAutoFocus={(e) => e.preventDefault()}
    >
      <header class="flex shrink-0 items-center gap-2 border-b border-gray-200 px-5 py-3 dark:border-white/10">
        <Dialog.Title class="text-dark/90 grow text-lg font-semibold">Add a version</Dialog.Title>
        <CloseButton class="-me-2" onclick={onClose} />
      </header>

      <div class="immich-scrollbar flex min-h-0 flex-col gap-3 overflow-y-auto px-5 py-4">
        <Text size="small" fontWeight="medium">Main image</Text>
        <RadioGroup.Root
          value={main}
          onValueChange={(v) => v && (main = v)}
          aria-label="Main image"
          class="flex flex-col gap-2"
        >
          {#each options as o (o.id)}
            <RadioGroup.Item
              value={o.id}
              class="data-[state=checked]:border-primary data-[state=checked]:bg-primary/5 focus-visible:ring-primary flex w-full cursor-pointer items-center gap-3 rounded-xl border border-gray-200 px-3 py-2 text-start transition-colors outline-none hover:bg-gray-50 focus-visible:ring-2 dark:border-white/10 dark:hover:bg-white/5"
            >
              {#snippet children({ checked })}
                {#if broken.has(o.id)}
                  <span class="bg-light-200 grid size-12 shrink-0 place-items-center rounded-lg text-gray-500">
                    <Icon icon={mdiImageOutline} size="1.5rem" />
                  </span>
                {:else}
                  <img
                    src={o.thumb}
                    alt=""
                    class="size-12 shrink-0 rounded-lg object-cover"
                    onerror={() => broken.add(o.id)}
                  />
                {/if}
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-sm font-medium">{o.name}</span>
                  <span class="block truncate text-xs text-gray-600 dark:text-gray-400">
                    {o.tags.filter(Boolean).join(' · ')}
                  </span>
                </span>
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
        <Text size="small" color="muted">
          {#if takesOver}
            Title, date, place and notes will come from {candidateName}, which is already in Gramps as
            {candidate.gramps_id}.{unsaved ? ' Your unsaved changes to this photo will be dropped.' : ''}
          {:else}
            Title, date, place and notes will come from {rec.title || rec.filename}.
          {/if}
        </Text>
      </div>

      <footer class="flex shrink-0 justify-end gap-2 border-t border-gray-200 px-5 py-3 dark:border-white/10">
        <Button variant="outline" color="secondary" onclick={onClose}>Cancel</Button>
        <Button onclick={() => onConfirm(main)}>{candidate.file ? 'Upload and add' : 'Add version'}</Button>
      </footer>
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
