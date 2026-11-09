// Tests fuer extension/popup.js: Meldung, wenn auf der Seite kein Projekt erkannt ist.
//
// Anlass: Auf der Claude-Projektuebersicht (/project/<id>) meldete das Popup
// "Kein ... Projekt erkannt", obwohl ein Projekt offen ist. Claude liefert das
// Projekt erst aus einer Unterhaltung (/chat/<id>).

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const SRC = fs.readFileSync(new URL('../../extension/popup.js', import.meta.url), 'utf8');
const PROJ = '22222222-2222-2222-2222-222222222222';
const C1 = 'aaaaaaaa-0000-0000-0000-000000000001';

const ALLGEMEIN = 'Kein ChatGPT- oder Claude-Projekt auf dieser Seite erkannt.';
const UEBERSICHT = 'Projektübersicht – Polaris erfasst erst, wenn ein Chat in diesem Projekt geöffnet ist.';
const OHNE_PROJEKT = 'Dieser Chat gehört zu keinem Projekt und wird nicht archiviert.';

// Laedt popup.js mit nachgebautem DOM und Browser-API. tab = aktiver Tab
// (null: keiner), context = Antwort auf get-context.
function loadPopup({ tab = null, context = null, stored = {} } = {}) {
  const elements = {};
  const element = (id) => {
    if (!elements[id]) {
      const classes = new Set(['hidden']);
      elements[id] = {
        textContent: '',
        checked: false,
        addEventListener() {},
        classList: {
          add: (c) => classes.add(c),
          remove: (c) => classes.delete(c),
          toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
          contains: (c) => classes.has(c),
        },
      };
    }
    return elements[id];
  };
  const browser = {
    tabs: { query: async () => (tab ? [tab] : []) },
    runtime: { sendMessage: (_msg, cb) => cb(context) },
    storage: { local: { get: (defaults, cb) => cb({ ...defaults, ...structuredClone(stored) }), set: (_p, cb) => cb() } },
    permissions: { contains: async () => true, request: async () => true },
  };
  const sandbox = { browser, document: { getElementById: element }, console, URL, Date };
  vm.createContext(sandbox);
  vm.runInContext(SRC, sandbox);
  return { sandbox, element };
}

test('noProjectText: Claude-Projektuebersicht', () => {
  const { sandbox } = loadPopup();
  assert.equal(sandbox.noProjectText(`https://claude.ai/project/${PROJ}`, null), UEBERSICHT);
});

test('noProjectText: Claude-Chat ohne Projekt', () => {
  const { sandbox } = loadPopup();
  assert.equal(sandbox.noProjectText(`https://claude.ai/chat/${C1}`, { conversationId: C1 }), OHNE_PROJEKT);
});

test('noProjectText: sonst die allgemeine Meldung', () => {
  const { sandbox } = loadPopup();
  assert.equal(sandbox.noProjectText('https://example.org/', null), ALLGEMEIN);
  // Ohne Host-Berechtigung fehlt tab.url.
  assert.equal(sandbox.noProjectText(undefined, null), ALLGEMEIN);
  // Projektpfad auf fremdem Host zaehlt nicht.
  assert.equal(sandbox.noProjectText(`https://example.org/project/${PROJ}`, null), ALLGEMEIN);
});

test('Popup zeigt auf der Projektuebersicht den Hinweis an', async () => {
  const { element } = loadPopup({ tab: { id: 1, url: `https://claude.ai/project/${PROJ}` }, context: {} });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(element('no-project').classList.contains('hidden'), false);
  assert.equal(element('no-project-text').textContent, UEBERSICHT);
});

// Seit 0.4.5: zwei Zeilen "dieser Chat" und "Projekt" (2026-11-09).
test('formatTime: heute nur Uhrzeit, sonst mit Datum', () => {
  const { sandbox } = loadPopup();
  const heute = new Date();
  heute.setHours(9, 5, 0, 0);
  assert.equal(sandbox.formatTime(heute.toISOString()).includes('.'), false);
  const frueher = new Date(2026, 10, 5, 9, 43).toISOString();
  assert.match(sandbox.formatTime(frueher), /05\.11\./);
  assert.equal(sandbox.formatTime(null), '-');
});

async function renderProject(stored) {
  const ctx = { projectId: 'claude-p-1', projectName: 'Protokolle', conversationId: 'c-offen' };
  const { element } = loadPopup({ tab: { id: 1, url: 'https://claude.ai/chat/c-offen' }, context: ctx, stored });
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
  return element;
}

test('Popup zeigt Chat- und Projektzeit getrennt', async () => {
  const element = await renderProject({
    lastExport: { 'claude-p-1': new Date(2026, 10, 9, 10, 29).toISOString() },
    lastExportChat: { 'c-offen': new Date(2026, 10, 5, 9, 43).toISOString(), 'c-anderer': new Date(2026, 10, 9, 10, 29).toISOString() },
  });
  assert.match(element('last-export-chat').textContent, /05\.11\./);
  assert.match(element('last-export').textContent, /09\.11\.|10:29/);
});

test('Popup: Chatzeit aus der Exportliste, solange noch kein eigener Vermerk da ist', async () => {
  const element = await renderProject({
    exportedMessages: { 'c-offen': { ids: ['m1'], at: new Date(2026, 10, 5, 9, 43).getTime() } },
  });
  assert.match(element('last-export-chat').textContent, /05\.11\./);
});

test('Popup: Chat noch nie exportiert', async () => {
  const element = await renderProject({ lastExportChat: { 'c-anderer': new Date().toISOString() } });
  assert.equal(element('last-export-chat').textContent, '-');
});
