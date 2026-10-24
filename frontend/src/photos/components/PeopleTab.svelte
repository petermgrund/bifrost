<script>
  import { Text } from '@immich/ui';
  import { plural } from '../lib/format.js';
  import ListCard from './ListCard.svelte';
  import ListRow from './ListRow.svelte';

  let { rec } = $props();
</script>

<div class="flex flex-col gap-3">
  <Text size="small" color="muted">{rec.people.length ? plural(rec.people.length, 'face') : 'No faces'}</Text>
  {#if rec.people.length}
    <ListCard>
      {#each rec.people as p (p.id)}
        <ListRow thumb="/faces/api/person-thumbnail/{p.id}" round>
          <p class="truncate text-sm font-medium">{p.name || '(unnamed)'}</p>
          {#if !p.linked}
            <p class="truncate text-xs text-gray-600 dark:text-gray-400">Not linked</p>
          {/if}
        </ListRow>
      {/each}
    </ListCard>
  {/if}
</div>
