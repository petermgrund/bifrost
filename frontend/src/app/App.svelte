<script>
  import { Alert, AppShell, AppShellHeader, Button, Heading, IconButton, LoadingSpinner, TooltipProvider } from '@immich/ui';
  import { mdiCogOutline, mdiFaceManOutline, mdiPlus, mdiTextRecognition, mdiWeatherNight, mdiWeatherSunny } from '@mdi/js';
  import BifrostMark from './components/BifrostMark.svelte';
  import CodeDialog from './components/CodeDialog.svelte';
  import Connections from './components/Connections.svelte';
  import FacesView from './components/FacesView.svelte';
  import Modal from './components/Modal.svelte';
  import PhotoEditor from './components/PhotoEditor.svelte';
  import PhotoPicker from './components/PhotoPicker.svelte';
  import Section from './components/Section.svelte';
  import { activity } from './lib/api.svelte.js';
  import { init, loadMedia, onRecord, store } from './lib/store.svelte.js';

  let editorId = $state(null);
  let coded = $state(null);
  let panel = $state('');
  let dark = $state(document.documentElement.classList.contains('dark'));

  const photos = $derived((store.media || []).filter((m) => m.immich.length));
  const documents = $derived((store.media || []).filter((m) => m.paperless.length));

  init();
  onRecord(() => loadMedia());

  function toggleTheme() {
    dark = !dark;
    document.documentElement.classList.toggle('dark', dark);
    localStorage.setItem('bifrost-theme', dark ? 'dark' : 'light');
  }
</script>

<TooltipProvider>
  <AppShell>
    <AppShellHeader border={false}>
      <div class="mx-auto flex w-full max-w-[110rem] items-center gap-3 px-4 md:px-6">
        <BifrostMark busy={activity.running > 0} />
        <Heading size="large" tag="h1" class="me-auto">Bifrost</Heading>
        <IconButton
          icon={dark ? mdiWeatherSunny : mdiWeatherNight}
          shape="round"
          variant="ghost"
          color="secondary"
          aria-label="Toggle dark mode"
          onclick={toggleTheme}
        />
        <IconButton
          icon={mdiCogOutline}
          shape="round"
          variant="ghost"
          color="secondary"
          aria-label="Connections"
          class="-me-2"
          onclick={() => (panel = 'connections')}
        />
      </div>
    </AppShellHeader>

    {#if store.config === null || (!store.error && store.media === null)}
      <div class="flex justify-center py-24"><LoadingSpinner size="giant" /></div>
    {:else if store.error}
      <div class="p-6"><Alert color="danger" title={store.error} /></div>
    {:else}
      <div class="mx-auto flex min-h-full w-full max-w-[110rem] flex-col gap-4 px-4 pt-2 pb-4 md:px-6 md:pb-6">
        {#if store.mediaError}<Alert color="danger" title={store.mediaError} />{/if}
        <div class="grid flex-1 auto-rows-fr gap-6 lg:grid-cols-2 lg:gap-8">
          {#if store.config.immich}
            <Section
              kind="immich"
              title="Immich photos"
              items={photos}
              onOpen={(m) => (editorId = m.immich[0].id)}
              onCode={(m) => (coded = m)}
            >
              {#snippet actions()}
                <Button
                  size="small"
                  variant="outline"
                  color="secondary"
                  leadingIcon={mdiFaceManOutline}
                  onclick={() => (panel = 'faces')}>Faces</Button
                >
                <Button size="small" variant="outline" color="secondary" leadingIcon={mdiPlus} onclick={() => (panel = 'picker')}>
                  Add
                </Button>
              {/snippet}
            </Section>
          {/if}
          {#if store.config.paperless}
            <Section
              kind="paperless"
              title="Paperless documents"
              items={documents}
              onOpen={(m) => (coded = m)}
              onCode={(m) => (coded = m)}
            >
              {#snippet actions({ running, run })}
                {#if store.config.ocr}
                  <Button
                    size="small"
                    variant="outline"
                    color="secondary"
                    leadingIcon={mdiTextRecognition}
                    disabled={running}
                    onclick={() => run({ path: '/sync/api/paperless/ocr', job: 'ocr', busy: 'Transcribing', idle: 'Nothing to transcribe' })}
                    >Run OCR</Button
                  >
                {/if}
              {/snippet}
            </Section>
          {/if}
        </div>
      </div>
    {/if}
  </AppShell>

  {#if panel === 'picker'}
    <PhotoPicker
      onClose={() => (panel = '')}
      onPick={(id) => {
        panel = '';
        editorId = id;
      }}
    />
  {:else if panel === 'faces'}
    <Modal title="Faces" size="large" onClose={() => (panel = '')}>
      <FacesView />
    </Modal>
  {:else if panel === 'connections'}
    <Connections onClose={() => (panel = '')} />
  {/if}

  {#if coded}
    <CodeDialog item={coded} onClose={() => (coded = null)} />
  {/if}

  {#if editorId}
    <PhotoEditor assetId={editorId} onClose={() => (editorId = null)} />
  {/if}
</TooltipProvider>
