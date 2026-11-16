<script>
  import { IconButton, Input } from '@immich/ui';
  import { mdiAccountOutline, mdiClose, mdiFaceMan, mdiMagnify } from '@mdi/js';
  import { store } from '../lib/store.svelte.js';
  import Modal from './Modal.svelte';
  import PhotoBrowser from './PhotoBrowser.svelte';
  import PickerPopover from './PickerPopover.svelte';
  import Segmented from './Segmented.svelte';

  let { onPick, onClose } = $props();

  const KEY = 'bifrost-add-account';
  const BOTH = '*';
  const accounts = store.config?.accounts || [];

  let q = $state('');
  let qDraft = $state('');
  let person = $state(null);
  let personQ = $state('');
  let account = $state(remembered());

  function remembered() {
    try {
      const label = localStorage.getItem(KEY) || '';
      return accounts.includes(label) ? label : '';
    } catch {
      return '';
    }
  }

  function pickAccount(value) {
    account = value === BOTH ? '' : value;
    person = null;
    try {
      localStorage.setItem(KEY, account);
    } catch {
      return;
    }
  }

  const personItems = $derived.by(() => {
    const needle = personQ.trim().toLowerCase();
    return (store.people || [])
      .filter((p) => (!account || p.account_label === account) && (!needle || p.name.toLowerCase().includes(needle)))
      .slice(0, 8)
      .map((p) => ({ id: p.id, label: p.name, sub: p.account_label, thumb: p.thumb, round: true }));
  });
</script>

<Modal title="Add a photo" size="large" {onClose}>
  <div class="flex flex-wrap items-center gap-2 px-5 pt-4">
    <div class="min-w-48 grow basis-0">
      <Input
        bind:value={qDraft}
        shape="round"
        leadingIcon={mdiMagnify}
        placeholder="Search titles and file names"
        aria-label="Search titles and file names"
        data-autofocus
        onkeydown={(e) => {
          if (e.key === 'Enter') q = qDraft.trim();
        }}
      />
    </div>
    {#if accounts.length > 1}
      <Segmented
        label="Account"
        value={account || BOTH}
        options={[...accounts.map((a) => ({ value: a, label: a })), { value: BOTH, label: 'Both' }]}
        onChange={pickAccount}
      />
    {/if}
    <PickerPopover
      label={person ? person.label : 'Person'}
      icon={person ? mdiFaceMan : mdiAccountOutline}
      shape="round"
      compact
      items={personItems}
      bind:query={personQ}
      placeholder="Search people"
      empty={store.people === null ? 'Loading people…' : 'No named person matches'}
      align="end"
      onPick={(p) => (person = p)}
    />
    {#if person}
      <IconButton
        icon={mdiClose}
        size="small"
        shape="round"
        variant="ghost"
        color="secondary"
        aria-label="Clear person"
        onclick={() => (person = null)}
      />
    {/if}
  </div>
  <PhotoBrowser mode="new" {q} {person} {account} onOpenPhoto={onPick} />
</Modal>
