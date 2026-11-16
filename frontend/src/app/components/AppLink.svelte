<script>
  import { Icon } from '@immich/ui';

  let { href, title, app = '', icon = undefined } = $props();
</script>

<a
  {href}
  {title}
  target="_blank"
  rel="noopener"
  class="hover:text-primary grid size-9 shrink-0 place-items-center rounded-full text-gray-600 transition-colors hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
>
  {#if app}
    <span class="app-icon size-6" style="--icon: url('/static/vendor/icons/{app}.svg')"></span>
  {:else}
    <Icon {icon} size="1.5rem" />
  {/if}
</a>
