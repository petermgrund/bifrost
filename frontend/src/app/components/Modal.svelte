<script>
  import { CloseButton } from '@immich/ui';
  import { Dialog } from 'bits-ui';

  let { title, size = 'small', onClose, children, heading = undefined, footer = undefined } = $props();

  const SIZES = {
    small: 'inset-0 m-auto h-fit max-h-[90dvh] w-[min(34rem,calc(100vw-2rem))] rounded-2xl border shadow-sm dark:border-white/10',
    large:
      'inset-0 sm:inset-x-4 sm:top-22 sm:bottom-4 sm:m-auto sm:max-h-[58rem] sm:max-w-[76rem] sm:rounded-2xl sm:border sm:shadow-sm sm:dark:border-white/10',
  };

  let content = $state(null);
</script>

<Dialog.Root
  open
  onOpenChange={(open) => {
    if (!open) onClose();
  }}
>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 z-40 bg-black/30 dark:bg-black/70" />
    <Dialog.Content
      bind:ref={content}
      class={['bg-light dark:bg-subtle fixed z-50 flex flex-col overflow-hidden outline-none', SIZES[size]]}
      onOpenAutoFocus={(e) => {
        e.preventDefault();
        (content?.querySelector('[data-autofocus]') || content)?.focus();
      }}
    >
      <header class="flex shrink-0 items-center gap-2 border-b border-gray-200 px-5 py-3 dark:border-white/10">
        <Dialog.Title class="text-dark/90 flex min-w-0 grow items-baseline gap-2 text-lg font-semibold">
          {#if heading}{@render heading()}{:else}<span class="truncate">{title}</span>{/if}
        </Dialog.Title>
        <CloseButton class="-me-2" onclick={onClose} />
      </header>
      <div class="immich-scrollbar flex min-h-0 flex-1 flex-col overflow-y-auto">
        {@render children()}
      </div>
      {#if footer}
        <footer class="flex shrink-0 items-center justify-end gap-2 border-t border-gray-200 px-5 py-3 dark:border-white/10">
          {@render footer()}
        </footer>
      {/if}
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
