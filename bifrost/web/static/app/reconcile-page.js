import { SyncPage } from './sync-page.js';

class ReconcilePage extends SyncPage {
  get apiBase() { return '/codes/api/reconcile'; }
  get jobName() { return 'codes.reconcile'; }
  get itemColLabel() { return 'Media'; }
  get lastColLabel() { return 'Code'; }
  get scanHeading() { return 'Check the register against Gramps, Immich and Paperless'; }
  get primaryEntity() { return 'media'; }
  get groups() { return [['create', 'Register'], ['update', 'Update']]; }
}
customElements.define('reconcile-page', ReconcilePage);
