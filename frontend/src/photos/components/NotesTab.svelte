<script>
  import { Textarea } from '@immich/ui';

  let { form = $bindable() } = $props();
</script>

<Textarea bind:value={form.notes} aria-label="Notes" rows={12} grow />
