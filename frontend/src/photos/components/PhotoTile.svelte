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
    title={item.filename}
    class={[
      'outline-primary bg-light-200 relative aspect-square cursor-pointer overflow-hidden rounded-xl outline-offset-2 focus-visible:outline-2',
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
      class="absolute inset-x-0 bottom-0 bg-linear-to-t from-black/80 via-black/40 to-transparent px-2.5 pt-10 pb-2 text-white"
    >
      <p class="line-clamp-2 text-sm leading-snug font-medium">{caption}</p>
      <p class="mt-0.5 flex justify-between gap-2 text-xs text-white/75">
        <span class={['truncate', item.gramps_id && 'font-mono']}>{item.gramps_id || 'Not in Gramps'}</span>
        <span class="shrink-0 font-mono">{item.date}</span>
      </p>
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
