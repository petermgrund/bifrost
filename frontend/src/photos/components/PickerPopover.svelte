<script>
  import { Button, Icon, LoadingSpinner } from '@immich/ui';
  import { mdiImageOutline, mdiMagnify } from '@mdi/js';
  import { Command, Popover } from 'bits-ui';
  import { SvelteSet } from 'svelte/reactivity';

  let {
    label,
    icon,
    items = [],
    query = $bindable(''),
    placeholder = 'Search',
    empty = '',
    loading = false,
    keepOpen = false,
    disabled = false,
    variant = 'outline',
    color = 'secondary',
    size = 'small',
    align = 'start',
    onPick,
    onOpen,
    onQuery,
  } = $props();

  let open = $state(false);
  const broken = new SvelteSet();

  function setQuery(value) {
    query = value;
    onQuery?.(value);
  }

  function onOpenChange(value) {
    if (value) onOpen?.();
    else setQuery('');
  }

  function pick(it) {
    if (!keepOpen) {
      open = false;
      setQuery('');
    }
    onPick(it);
  }
</script>

<Popover.Root bind:open {onOpenChange}>
  <Popover.Trigger {disabled}>
    {#snippet child({ props })}
      <Button {...props} {variant} {color} {size} leadingIcon={icon} {disabled}>
        <span class="max-w-72 truncate">{label}</span>
      </Button>
    {/snippet}
  </Popover.Trigger>
  <Popover.Portal>
    <Popover.Content
      {align}
      sideOffset={6}
      collisionPadding={12}
      class="bg-light-100 text-dark dark:border-light-300 z-70 w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-xl border shadow-lg outline-none"
    >
      <Command.Root shouldFilter={false} loop>
        <div class="p-2">
          <div
            class="focus-within:ring-primary flex items-center rounded-lg bg-gray-100 ring-1 ring-gray-200 transition dark:bg-gray-800 dark:ring-neutral-700"
          >
            <Icon icon={mdiMagnify} size="1.25rem" class="mx-2.5 shrink-0 text-gray-500" />
            <Command.Input
              value={query}
              oninput={(e) => setQuery(e.currentTarget.value)}
              {placeholder}
              class="w-full bg-transparent py-2 pe-3 text-sm outline-none"
            />
          </div>
        </div>
        <Command.List class="immich-scrollbar max-h-80 overflow-y-auto px-1 pb-1">
          {#if loading}
            <div class="flex justify-center p-3"><LoadingSpinner /></div>
          {:else if !items.length && empty}
            <p class="px-3 pt-1 pb-2 text-sm text-gray-600 dark:text-gray-400">{empty}</p>
          {/if}
          {#each items as it (it.id)}
            <Command.Item
              value={String(it.id)}
              disabled={it.disabled}
              onSelect={() => pick(it)}
              class="data-selected:bg-light-200 dark:data-selected:bg-primary-200 flex cursor-pointer items-center gap-3 rounded-lg px-2 py-1.5 outline-none select-none data-disabled:cursor-not-allowed data-disabled:opacity-50"
            >
              {#if it.thumb && !broken.has(it.id)}
                <img
                  src={it.thumb}
                  alt=""
                  class={['size-10 shrink-0 object-cover', it.round ? 'rounded-full' : 'rounded-md']}
                  onerror={() => broken.add(it.id)}
                />
              {:else if it.icon || it.thumb}
                <span class="grid size-10 shrink-0 place-items-center text-gray-600 dark:text-gray-400">
                  <Icon icon={it.icon || mdiImageOutline} size="1.375rem" />
                </span>
              {/if}
              <div class="min-w-0">
                <p class="truncate text-sm font-medium">{it.label}</p>
                {#if it.sub}
                  <p class="truncate text-xs text-gray-600 dark:text-gray-400">{it.sub}</p>
                {/if}
              </div>
            </Command.Item>
          {/each}
        </Command.List>
      </Command.Root>
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>
