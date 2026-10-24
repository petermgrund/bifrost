<script>
  let { children } = $props();
</script>

<ul class="flex flex-col divide-y divide-gray-200 rounded-xl border border-gray-200 dark:divide-white/10 dark:border-white/10">
  {@render children()}
</ul>
