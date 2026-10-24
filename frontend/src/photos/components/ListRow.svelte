<script>
  import { Icon } from '@immich/ui';

  let { thumb = '', round = false, icon = undefined, onView = undefined, children, trailing = undefined } = $props();
</script>

{#snippet picture()}
  <img
    src={thumb}
    alt=""
    loading="lazy"
    class={['size-12 bg-gray-200 object-cover dark:bg-gray-700', round ? 'rounded-full' : 'rounded-lg']}
  />
{/snippet}

<li class="flex items-center gap-3 px-3 py-2">
  {#if thumb && onView}
    <button type="button" class="shrink-0 cursor-zoom-in" title="View larger" onclick={onView}>{@render picture()}</button>
  {:else if thumb}
    <span class="shrink-0">{@render picture()}</span>
  {:else if icon}
    <span class="grid size-12 shrink-0 place-items-center rounded-lg bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
      <Icon {icon} size="1.5rem" />
    </span>
  {/if}
  <div class="min-w-0 flex-1">{@render children()}</div>
  {@render trailing?.()}
</li>
