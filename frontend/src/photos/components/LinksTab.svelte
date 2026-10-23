<script>
  import { Button, IconButton, Input } from '@immich/ui';
  import { mdiClose, mdiLinkPlus } from '@mdi/js';

  let { rec, busy, onAdd, onRemove } = $props();

  let url = $state('');

  const links = $derived(rec.links || []);

  async function add(e) {
    e.preventDefault();
    const value = url.trim();
    if (!value || busy) return;
    if (await onAdd(value)) url = '';
  }
</script>

<div class="flex flex-col gap-3">
  <form class="flex items-center gap-2" onsubmit={add}>
    <div class="min-w-0 grow">
      <Input bind:value={url} placeholder="https://" aria-label="Link" disabled={!!busy} />
    </div>
    <Button type="submit" variant="outline" color="secondary" leadingIcon={mdiLinkPlus} disabled={!url.trim() || !!busy}>
      Add link
    </Button>
  </form>
  {#if links.length}
    <ul class="flex flex-col">
      {#each links as l (l.id)}
        <li class="hover:bg-light-100 flex items-center gap-2 rounded-xl px-3 py-1">
          <a href={l.url} target="_blank" rel="noopener" title={l.url} class="hover:text-primary grow truncate text-sm">
            {l.url}
          </a>
          <IconButton
            icon={mdiClose}
            size="small"
            shape="round"
            variant="ghost"
            color="secondary"
            aria-label="Remove {l.url}"
            disabled={!!busy}
            onclick={() => onRemove(l)}
          />
        </li>
      {/each}
    </ul>
  {/if}
</div>
