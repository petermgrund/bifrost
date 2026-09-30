<script>
  import { FormModal, Input, ListButton, Text } from '@immich/ui';
  import { mdiSync } from '@mdi/js';

  let { codes, onClose } = $props();

  let picked = $state('');
  let q = $state('');

  const shown = $derived.by(() => {
    const text = q.trim().toLowerCase();
    if (!text) return codes;
    const bare = text.replace(/[\s-]+/g, '').toUpperCase();
    return codes.filter((c) => (bare && c.code.includes(bare))
      || [c.note, c.notes].some((v) => v && v.toLowerCase().includes(text)));
  });
</script>

<FormModal
  title="Sync to Gramps"
  icon={mdiSync}
  size="medium"
  submitText={picked ? `Sync as ${picked}` : 'Sync with a new code'}
  onClose={() => onClose()}
  onSubmit={() => onClose(picked || null)}
>
  <div class="flex flex-col gap-3">
    <ListButton selected={!picked} onclick={() => (picked = '')}>Generate a new code</ListButton>
    {#if codes.length > 6}
      <Input bind:value={q} placeholder="Search codes, descriptions and notes" />
    {/if}
    <div class="immich-scrollbar flex max-h-80 flex-col gap-1 overflow-y-auto">
      {#each shown as c (c.code)}
        <ListButton selected={picked === c.code} onclick={() => (picked = c.code)}>
          <div class="flex min-w-0 flex-col items-start gap-0.5 text-left">
            <span class="font-mono">{c.code}</span>
            {#if c.note}<span class="text-sm">{c.note}</span>{/if}
          </div>
        </ListButton>
      {:else}
        <Text size="small" color="muted">No codes match.</Text>
      {/each}
    </div>
  </div>
</FormModal>
