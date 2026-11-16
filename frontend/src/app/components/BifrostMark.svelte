<script>
  let { busy = false } = $props();
</script>

<svg class={['mark', busy && 'busy']} width="45" height="33" viewBox="0 0 30 22" aria-hidden="true">
  <g fill="none" stroke-width="2.6" stroke-linecap="round">
    <g class="track">
      <path d="M3 20 A12 12 0 0 1 27 20" stroke="var(--arc-0)" />
      <path d="M7 20 A8 8 0 0 1 23 20" stroke="var(--arc-1)" />
      <path d="M11 20 A4 4 0 0 1 19 20" stroke="var(--arc-2)" />
    </g>
    <g class="run">
      <path d="M3 20 A12 12 0 0 1 27 20" stroke="var(--arc-0)" style="--to:37.699px;stroke-dasharray:37.699 37.699" />
      <path
        d="M7 20 A8 8 0 0 1 23 20"
        stroke="var(--arc-1)"
        style="--to:25.133px;stroke-dasharray:25.133 25.133;animation-delay:.16s"
      />
      <path
        d="M11 20 A4 4 0 0 1 19 20"
        stroke="var(--arc-2)"
        style="--to:12.566px;stroke-dasharray:12.566 12.566;animation-delay:.32s"
      />
    </g>
  </g>
</svg>

<style>
  .mark {
    --arc-0: #9a4523;
    --arc-1: #b07a00;
    --arc-2: #4a5bae;
    flex: none;
  }
  :global(.dark) .mark {
    --arc-0: #ffb59a;
    --arc-1: #ddb15f;
    --arc-2: #b6c4ff;
  }
  .run {
    opacity: 0;
  }
  .busy .track {
    opacity: 0.2;
  }
  .busy .run {
    opacity: 1;
  }
  .busy .run > path {
    animation: draw 2s cubic-bezier(0.5, 0, 0.2, 1) infinite;
  }
  @keyframes draw {
    0% {
      stroke-dashoffset: 0;
      opacity: 1;
    }
    13% {
      stroke-dashoffset: 0;
      opacity: 0;
    }
    14% {
      stroke-dashoffset: var(--to);
      opacity: 0;
    }
    26% {
      opacity: 1;
    }
    69% {
      stroke-dashoffset: 0;
    }
    100% {
      stroke-dashoffset: 0;
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .busy .run > path {
      animation: none;
    }
    .busy .track {
      opacity: 1;
    }
  }
</style>
