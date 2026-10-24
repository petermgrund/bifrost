<script>
  import { Button, IconButton, Input } from '@immich/ui';
  import { mdiClose, mdiLinkPlus } from '@mdi/js';
  import { LINK_RE } from '../lib/format.js';

  let { form = $bindable(), busy, onError } = $props();

  let url = $state('');

  function add(e) {
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

  function remove(value) {
    form.links = form.links.filter((l) => l !== value);
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
  {#if form.links.length}
    <ul class="flex flex-col">
      {#each form.links as l (l)}
        <li class="hover:bg-light-100 flex items-center gap-2 rounded-xl px-3 py-1">
          <a href={l} target="_blank" rel="noopener" title={l} class="hover:text-primary grow truncate text-sm">
            {l}
          </a>
          <IconButton
            icon={mdiClose}
            size="small"
            shape="round"
            variant="ghost"
            color="secondary"
            aria-label="Remove {l}"
            disabled={!!busy}
            onclick={() => remove(l)}
          />
        </li>
      {/each}
    </ul>
  {/if}
</div>
