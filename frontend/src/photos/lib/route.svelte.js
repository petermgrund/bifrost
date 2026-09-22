const VIEWS = ['recent', 'tagged', 'synced', 'collections'];

function parse() {
  const [name, id] = window.location.hash.replace(/^#\/?/, '').split('/');
  const view = VIEWS.includes(name) ? name : 'recent';
  return { view, collection: view === 'collections' && id ? Number(id) : null };
}

export const route = $state(parse());

window.addEventListener('hashchange', () => Object.assign(route, parse()));
