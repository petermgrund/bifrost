<script>
  import {
    Alert,
    AppShell,
    AppShellHeader,
    AppShellSidebar,
    IconButton,
    Input,
    LoadingSpinner,
    NavbarGroup,
    NavbarItem,
    TooltipProvider,
  } from '@immich/ui';
  import {
    mdiBookmarkMultiple,
    mdiBookmarkMultipleOutline,
    mdiCheckCircle,
    mdiCheckCircleOutline,
    mdiClockOutline,
    mdiClockTimeFour,
    mdiClose,
    mdiMagnify,
    mdiMenu,
    mdiTag,
    mdiTagOutline,
    mdiWeatherNight,
    mdiWeatherSunny,
  } from '@mdi/js';
  import BifrostMark from './components/BifrostMark.svelte';
  import CollectionView from './components/CollectionView.svelte';
  import CollectionsList from './components/CollectionsList.svelte';
  import PhotoBrowser from './components/PhotoBrowser.svelte';
  import PhotoEditor from './components/PhotoEditor.svelte';
  import { activity } from './lib/api.svelte.js';
  import { route } from './lib/route.svelte.js';
  import { init, store } from './lib/store.svelte.js';

  const NAV = [
    { id: 'recent', title: 'Recent', icon: mdiClockOutline, activeIcon: mdiClockTimeFour },
    { id: 'tagged', title: 'Tagged for sync', icon: mdiTagOutline, activeIcon: mdiTag },
    { id: 'synced', title: 'In Gramps', icon: mdiCheckCircleOutline, activeIcon: mdiCheckCircle },
  ];
  const wide = window.matchMedia('(min-width: 768px)');

  let sidebarOpen = $state(wide.matches);
  let collectionsOpen = $state(true);
  let q = $state('');
  let qDraft = $state('');
  let person = $state(null);
  let editorId = $state(null);
  let dark = $state(document.documentElement.classList.contains('dark'));

  const collectionNav = $derived(
    (store.collections || []).map((c) => ({
      title: c.name,
      href: `#/collections/${c.id}`,
      active: route.view === 'collections' && route.collection === c.id,
      variant: 'compact',
    })),
  );

  init();

  window.addEventListener('hashchange', () => {
    editorId = null;
    if (!wide.matches) sidebarOpen = false;
  });

  function search() {
    q = qDraft.trim();
    if (route.view === 'collections') window.location.hash = '#/recent';
  }

  function clearSearch() {
    q = '';
    qDraft = '';
  }

  function toggleTheme() {
    dark = !dark;
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('bifrost-theme', dark ? 'dark' : 'light');
  }
</script>

{#snippet clearButton()}
  <IconButton
    icon={mdiClose}
    size="tiny"
    shape="round"
    variant="ghost"
    color="secondary"
    aria-label="Clear search"
    onclick={clearSearch}
  />
{/snippet}

<TooltipProvider>
  <AppShell>
    <AppShellHeader>
      <div class="flex w-full items-center gap-2 px-2 md:px-4">
        <IconButton
          icon={mdiMenu}
          shape="round"
          variant="ghost"
          color="secondary"
          aria-label="Toggle the sidebar"
          onclick={() => (sidebarOpen = !sidebarOpen)}
        />
        <a href="/" class="flex shrink-0 items-center gap-2" title="Back to Bifrost">
          <BifrostMark busy={activity.running > 0} />
          <span class="hidden text-xl font-semibold tracking-tight sm:inline">Bifrost</span>
        </a>
        <span class="hidden text-xl text-gray-400 sm:inline">/</span>
        <span class="shrink-0 text-xl font-semibold tracking-tight">Photos</span>
        <div class="mx-auto w-full max-w-xl px-2">
          <Input
            bind:value={qDraft}
            shape="round"
            leadingIcon={mdiMagnify}
            trailingIcon={qDraft ? clearButton : undefined}
            placeholder="Search titles and file names"
            aria-label="Search titles and file names"
            onkeydown={(e) => {
              if (e.key === 'Enter') search();
              else if (e.key === 'Escape') clearSearch();
            }}
          />
        </div>
        <IconButton
          icon={dark ? mdiWeatherSunny : mdiWeatherNight}
          shape="round"
          variant="ghost"
          color="secondary"
          aria-label="Toggle dark mode"
          onclick={toggleTheme}
        />
      </div>
    </AppShellHeader>

    <AppShellSidebar bind:open={sidebarOpen}>
      <nav class="flex flex-col pt-4 pe-4">
        {#each NAV as item (item.id)}
          <NavbarItem
            title={item.title}
            href="#/{item.id}"
            icon={item.icon}
            activeIcon={item.activeIcon}
            active={route.view === item.id}
          />
        {/each}
        <NavbarGroup title="Library" />
        <NavbarItem
          title="Collections"
          href="#/collections"
          icon={mdiBookmarkMultipleOutline}
          activeIcon={mdiBookmarkMultiple}
          active={route.view === 'collections' && !route.collection}
          bind:expanded={collectionsOpen}
          items={collectionNav.length ? collectionNav : undefined}
        />
      </nav>
    </AppShellSidebar>

    {#if store.config === null}
      <div class="flex justify-center py-24"><LoadingSpinner size="giant" /></div>
    {:else if !store.config.enabled}
      <div class="p-6">
        <Alert color="warning" title={store.error || 'Immich is not configured (immich.base_url / accounts)'} />
      </div>
    {:else if route.view === 'collections'}
      {#if route.collection}
        <CollectionView id={route.collection} onOpenPhoto={(id) => (editorId = id)} />
      {:else}
        <CollectionsList />
      {/if}
    {:else}
      <PhotoBrowser
        mode={route.view}
        {q}
        {person}
        onPerson={(p) => (person = p)}
        onClearQuery={clearSearch}
        onOpenPhoto={(id) => (editorId = id)}
      />
    {/if}
  </AppShell>

  {#if editorId}
    <PhotoEditor assetId={editorId} onClose={() => (editorId = null)} />
  {/if}
</TooltipProvider>
