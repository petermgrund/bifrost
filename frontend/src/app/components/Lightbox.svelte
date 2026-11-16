<script>
  import { IconButton } from '@immich/ui';
  import { mdiClose } from '@mdi/js';
  import { Dialog } from 'bits-ui';
  import { sizeText } from '../lib/format.js';

  let { item, onClose } = $props();

  let content = $state(null);
</script>

<Dialog.Root
  open={!!item}
  onOpenChange={(open) => {
    if (!open) onClose();
  }}
>
  <Dialog.Portal>
    <Dialog.Overlay class="fixed inset-0 z-60 bg-black/90" />
    <Dialog.Content
      bind:ref={content}
      class="fixed inset-0 z-60 flex flex-col items-center justify-center gap-3 p-4 outline-none"
      onOpenAutoFocus={(e) => {
        e.preventDefault();
        content?.focus();
      }}
      onclick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {#if item}
        <img
          src="/photos/api/thumb/{item.asset_id}?size=preview"
          alt=""
          class="min-h-0 max-w-full flex-1 rounded-lg object-contain"
        />
        <div class="flex w-full max-w-5xl items-center gap-3 text-sm text-white/90">
          <Dialog.Title class="flex min-w-0 grow items-baseline gap-3 font-normal">
            <span class={['truncate', !item.label && 'font-mono']}>{item.label || item.filename}</span>
            <span class="shrink-0 font-mono text-white/50">{sizeText(item)}</span>
          </Dialog.Title>
          <IconButton
            icon={mdiClose}
            shape="round"
            variant="ghost"
            color="secondary"
            class="text-white not-disabled:hover:bg-white/10"
            aria-label="Close"
            onclick={onClose}
          />
        </div>
      {/if}
    </Dialog.Content>
  </Dialog.Portal>
</Dialog.Root>
