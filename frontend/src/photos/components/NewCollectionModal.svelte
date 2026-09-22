<script>
  import { Field, FormModal, Input, Text, Textarea } from '@immich/ui';
  import { mdiBookmarkPlusOutline } from '@mdi/js';
  import { post } from '../lib/api.svelte.js';

  let { onClose } = $props();

  let name = $state('');
  let description = $state('');
  let error = $state('');
  let nameRef = $state(null);

  $effect(() => {
    nameRef?.focus();
  });

  async function onSubmit() {
    error = '';
    try {
      onClose(await post('/photos/api/collections', { name: name.trim(), description: description.trim() }));
    } catch (e) {
      error = e.message;
    }
  }
</script>

<FormModal
  title="Create collection"
  icon={mdiBookmarkPlusOutline}
  submitText="Create"
  disabled={!name.trim()}
  onClose={() => onClose()}
  {onSubmit}
>
  <div class="flex flex-col gap-4">
    <Field label="Name">
      <Input bind:ref={nameRef} bind:value={name} />
    </Field>
    <Field label="Description">
      <Textarea bind:value={description} rows={3} />
    </Field>
    {#if error}<Text size="small" color="danger">{error}</Text>{/if}
  </div>
</FormModal>
