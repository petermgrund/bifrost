<script>
  import { Icon } from '@immich/ui';
  import { mdiFileDocumentOutline, mdiImageOutline } from '@mdi/js';
  import { mediaThumb } from '../lib/format.js';

  let { item, class: className = 'size-12' } = $props();

  let broken = $state(false);
</script>

{#if broken}
  <span class={['grid shrink-0 place-items-center rounded-lg bg-gray-100 text-gray-500 dark:bg-gray-800', className]}>
    <Icon icon={item.immich.length ? mdiImageOutline : mdiFileDocumentOutline} size="1.5rem" />
  </span>
{:else}
  <img
    src={mediaThumb(item)}
    alt=""
    loading="lazy"
    class={['shrink-0 rounded-lg bg-gray-200 object-cover dark:bg-gray-700', className]}
    onerror={() => (broken = true)}
  />
{/if}
