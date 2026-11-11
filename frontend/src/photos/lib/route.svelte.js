const VIEWS = ['recent', 'synced', 'faces'];

function parse() {
  const [name] = window.location.hash.replace(/^#\/?/, '').split('/');
  return { view: VIEWS.includes(name) ? name : 'recent' };
}

export const route = $state(parse());

window.addEventListener('hashchange', () => Object.assign(route, parse()));
