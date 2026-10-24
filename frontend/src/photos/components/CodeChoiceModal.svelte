<script>
  import { FormModal, Input, ListButton, Text } from '@immich/ui';
  import { mdiContentSaveOutline } from '@mdi/js';

  let { codes, onClose } = $props();

  let picked = $state('');
  let q = $state('');

  const shown = $derived.by(() => {
    const bare = q.replace(/[\s-]+/g, '').toUpperCase();
    return bare ? codes.filter((c) => c.code.includes(bare)) : codes;
  });
</script>

<FormModal
  title="Add to Gramps"
  icon={mdiContentSaveOutline}
  size="medium"
  submitText={picked ? `Add as ${picked}` : 'Add with a new code'}
  onClose={() => onClose()}
  onSubmit={() => onClose(picked || null)}
>
  <div class="flex flex-col gap-3">
    <ListButton selected={!picked} onclick={() => (picked = '')}>Generate a new code</ListButton>
    {#if codes.length > 6}
      <Input bind:value={q} placeholder="Search codes" />
    {/if}
    <div class="immich-scrollbar flex max-h-80 flex-col gap-1 overflow-y-auto">
      {#each shown as c (c.code)}
        <ListButton selected={picked === c.code} onclick={() => (picked = c.code)}>
          <span class="font-mono">{c.code}</span>
        </ListButton>
      {:else}
        <Text size="small" color="muted">No codes match.</Text>
      {/each}
    </div>
  </div>
</FormModal>
