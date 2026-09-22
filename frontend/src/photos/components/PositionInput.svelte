<script>
  let { position, max, label, disabled = false, onMove } = $props();

  let draft = $state(null);

  function commit() {
    if (draft === null) return;
    const wanted = Number.parseInt(draft, 10);
    draft = null;
    if (Number.isNaN(wanted)) return;
    const clamped = Math.min(Math.max(wanted, 1), max);
    if (clamped !== position) onMove(clamped);
  }

  function onkeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      commit();
      e.currentTarget.blur();
    } else if (e.key === 'Escape') {
      e.stopPropagation();
      draft = null;
      e.currentTarget.blur();
    }
  }
</script>

<input
  type="text"
  inputmode="numeric"
  autocomplete="off"
  aria-label="Slot of {label}"
  title="Slot: type a number, then Enter"
  {disabled}
  value={draft ?? String(position)}
  size={Math.max(String(draft ?? position).length, 1)}
  class="focus:bg-light focus:text-dark focus:ring-primary h-7 min-w-8 cursor-text rounded-full bg-black/55 px-2 text-center font-mono text-sm text-white tabular-nums ring-1 ring-white/30 backdrop-blur-sm transition outline-none hover:bg-black/75 focus:ring-2 disabled:opacity-60"
  onfocus={(e) => e.currentTarget.select()}
  oninput={(e) => {
    draft = e.currentTarget.value.replace(/\D/g, '');
    e.currentTarget.value = draft;
  }}
  onblur={commit}
  {onkeydown}
/>
