<script>
  import { Button, Icon, LoadingSpinner, Text } from '@immich/ui';
  import { mdiAlertCircleOutline, mdiCheckCircleOutline, mdiMinusCircleOutline, mdiRefresh } from '@mdi/js';
  import { get } from '../lib/api.svelte.js';
  import Modal from './Modal.svelte';

  let { onClose } = $props();

  let status = $state(null);
  let busy = $state(false);
  let error = $state('');

  async function load() {
    busy = true;
    error = '';
    try {
      status = await get('/config/api/status');
    } catch (e) {
      error = e.message;
    } finally {
      busy = false;
    }
  }

  load();
</script>

<Modal title="Connections" {onClose}>
  <div class="flex flex-col gap-3 px-5 py-4">
    {#if error}<Text size="small" color="danger">{error}</Text>{/if}
    {#if !status}
      {#if !error}<div class="flex justify-center py-8"><LoadingSpinner size="large" /></div>{/if}
    {:else}
      <ul class="flex flex-col gap-2">
        {#each status.services as s (s.key)}
          <li class="flex items-center gap-3 text-sm">
            <span class={s.ok ? 'text-success' : s.ok === false ? 'text-danger' : 'text-gray-400'}>
              <Icon
                icon={s.ok ? mdiCheckCircleOutline : s.ok === false ? mdiAlertCircleOutline : mdiMinusCircleOutline}
                size="1.25rem"
              />
            </span>
            <span class="shrink-0 font-medium">{s.name}</span>
            <span class={['min-w-0 flex-1', s.ok === false ? 'text-danger' : 'truncate text-gray-600 dark:text-gray-400']}>
              {s.detail}
            </span>
          </li>
        {/each}
      </ul>
      <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 border-t border-gray-200 pt-3 text-sm dark:border-white/10">
        <dt class="text-gray-600 dark:text-gray-400">Version</dt>
        <dd class="font-mono text-xs">{status.version}</dd>
        <dt class="text-gray-600 dark:text-gray-400">Config file</dt>
        <dd class="font-mono text-xs break-all">{status.config_path}</dd>
      </dl>
    {/if}
  </div>
  {#snippet footer()}
    <Button variant="outline" color="secondary" leadingIcon={mdiRefresh} disabled={busy} onclick={load}>Check again</Button>
  {/snippet}
</Modal>
