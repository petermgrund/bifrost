<script>
  import { RadioGroup } from 'bits-ui';

  let { options, value, label, onChange } = $props();
</script>

<RadioGroup.Root
  {value}
  onValueChange={(v) => v && onChange(v)}
  orientation="horizontal"
  aria-label={label}
  class="inline-flex w-fit rounded-lg bg-gray-100 p-0.5 ring-1 ring-gray-200 dark:bg-gray-800 dark:ring-neutral-700"
>
  {#each options as o (o.value)}
    <RadioGroup.Item
      value={o.value}
      class="data-[state=checked]:bg-light data-[state=checked]:text-primary hover:text-dark focus-visible:ring-primary cursor-pointer rounded-md px-3 py-1 text-sm font-medium text-gray-600 transition-colors outline-none focus-visible:ring-2 data-[state=checked]:shadow-sm dark:text-gray-400 dark:data-[state=checked]:bg-gray-700"
    >
      {o.label}
    </RadioGroup.Item>
  {/each}
</RadioGroup.Root>
