<script>
  import { Icon } from '@immich/ui';
  import { mdiCameraBurst, mdiImageBrokenVariant, mdiPlayCircleOutline } from '@mdi/js';

  let { item, onOpen, highlight = false, topLeft, topRight } = $props();

  const caption = $derived(item.title || item.filename || 'Untitled');

  function onkeydown(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onOpen();
    }
  }
</script>

<div class="group relative">
  <div
    role="button"
    tabindex="0"
    class={[
      'outline-primary bg-light-200 relative aspect-square cursor-pointer overflow-hidden outline-offset-2 focus-visible:outline-2',
      highlight && 'ring-primary ring-4',
    ]}
    onclick={onOpen}
    {onkeydown}
  >
    {#if item.missing}
      <div class="absolute inset-0 grid place-items-center text-gray-400">
        <Icon icon={mdiImageBrokenVariant} size="2.5rem" />
      </div>
    {:else}
      <img
        src={item.thumb}
        alt=""
        loading="lazy"
        draggable="false"
        class="size-full object-cover transition duration-300 group-hover:scale-[1.03]"
      />
    {/if}
    <div
      class="pointer-events-none absolute inset-x-0 bottom-0 bg-linear-to-t from-black/80 via-black/40 to-transparent px-2.5 pt-10 pb-2 text-white opacity-0 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
    >
      <p class="line-clamp-2 text-sm leading-snug font-medium">{caption}</p>
      {#if item.gramps_id}
        <p class="mt-0.5 truncate font-mono text-xs text-white/75">{item.gramps_id}</p>
      {/if}
    </div>
  </div>
  {#if topLeft}
    <div class="absolute top-2 left-2">{@render topLeft()}</div>
  {/if}
  <div class="absolute top-2 right-2 flex items-center gap-1">
    {#if item.type === 'VIDEO'}
      <span class="pointer-events-none rounded-full bg-black/55 p-1 text-white backdrop-blur-sm">
        <Icon icon={mdiPlayCircleOutline} size="1rem" />
      </span>
    {/if}
    {#if item.versions > 1}
      <span
        class="pointer-events-none flex items-center gap-1 rounded-full bg-black/55 px-2 py-1 font-mono text-xs text-white backdrop-blur-sm"
        title="Versions"
      >
        <Icon icon={mdiCameraBurst} size="0.875rem" />{item.versions}
      </span>
    {/if}
    {@render topRight?.()}
  </div>
</div>
