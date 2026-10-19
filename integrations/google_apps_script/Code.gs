/**
 * THIGAS Hub - ponte Google Drive (Google Apps Script).
 * Propriedades do script: HUB_SECRET (>=32 caracteres) e ALLOWED_FOLDER_IDS (IDs separados por vírgula).
 * Implantar como app da Web: executar como "Eu", acesso "Qualquer pessoa".
 * ATENÇÃO: endpoint público; a autenticação é feita pelo segredo no corpo POST.
 * Não coloque o segredo no código, URL, logs, arquivos ou GitHub.
 */
function doGet() {
  return output_(false, null);
}

function doPost(event) {
  try {
    if (!event || !event.postData || !event.postData.contents ||
        event.postData.contents.length > 18000) return output_(false, null);
    const message = JSON.parse(event.postData.contents);
    const properties = PropertiesService.getScriptProperties();
    const key = properties.getProperty('HUB_SECRET') || '';
    if (key.length < 32 || !sameSecret_(message.secret, key)) return output_(false, null);
    const roots = allowedRoots_();
    const operation = message.action;
    const payload = message.payload;
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return output_(false, null);

    if (operation === 'search') return output_(true, search_(roots, payload));
    if (operation !== 'document.create' && operation !== 'spreadsheet.create' &&
        operation !== 'presentation.create') return output_(false, null);

    const lock = LockService.getScriptLock();
    if (!lock.tryLock(20000)) return output_(false, null);
    try {
      const destination = authorizedFolder_(roots, payload.folder_id);
      return output_(true, create_(operation, payload, destination));
    } finally {
      lock.releaseLock();
    }
  } catch (error) {
    // Never return credentials, folder IDs, user content or internal exception messages.
    return output_(false, null);
  }
}

function output_(ok, data) {
  return ContentService.createTextOutput(JSON.stringify({ok: ok, data: data}))
    .setMimeType(ContentService.MimeType.JSON);
}

function sameSecret_(candidate, expected) {
  const left = typeof candidate === 'string' ? candidate : '';
  let diff = left.length ^ expected.length;
  for (let i = 0; i < Math.max(left.length, expected.length); i++) {
    diff |= (left.charCodeAt(i) || 0) ^ (expected.charCodeAt(i) || 0);
  }
  return diff === 0;
}

function allowedRoots_() {
  const raw = PropertiesService.getScriptProperties().getProperty('ALLOWED_FOLDER_IDS') || '';
  const ids = raw.split(',').map(id => id.trim()).filter(Boolean);
  if (!ids.length || ids.length > 10 ||
      ids.some(id => !/^[A-Za-z0-9_-]{10,160}$/.test(id))) {
    throw new Error('Configure ALLOWED_FOLDER_IDS com IDs válidos de pastas.');
  }
  return ids;
}

function authorizedFolder_(roots, requestedId) {
  const id = requestedId == null || requestedId === '' ? roots[0] : String(requestedId);
  if (!/^[A-Za-z0-9_-]{10,160}$/.test(id)) throw new Error('Pasta inválida.');
  const folder = DriveApp.getFolderById(id);
  if (roots.indexOf(id) >= 0) return folder;
  let frontier = [folder];
  const checked = {};
  for (let depth = 0; depth < 20 && frontier.length; depth++) {
    const parents = [];
    for (const node of frontier) {
      const it = node.getParents();
      while (it.hasNext()) {
        const parent = it.next();
        const parentId = parent.getId();
        if (roots.indexOf(parentId) >= 0) return folder;
        if (!checked[parentId]) {
          checked[parentId] = true;
          parents.push(parent);
        }
      }
    }
    frontier = parents.slice(0, 50);
  }
  throw new Error('Fora das pastas autorizadas.');
}

function search_(roots, payload) {
  const phrase = String(payload.query || '').trim().toLowerCase().slice(0, 150);
  if (phrase.length < 2) throw new Error('Informe termos de busca.');
  const listFolders = phrase === 'pastas' || phrase === 'listar pastas';
  const queue = roots.map(id => DriveApp.getFolderById(id));
  const visited = {};
  const result = [];
  let scannedFiles = 0;

  while (queue.length && Object.keys(visited).length < 50 && result.length < 10) {
    const folder = queue.shift();
    const id = folder.getId();
    if (visited[id]) continue;
    visited[id] = true;
    const name = folder.getName();
    if (listFolders || name.toLowerCase().includes(phrase)) {
      result.push({title: name, detail: 'Pasta',
                   summary: 'Pasta autorizada', url: folder.getUrl()});
      if (result.length >= 10) break;
    }
    const files = folder.getFiles();
    while (files.hasNext() && scannedFiles < 300 && result.length < 10) {
      const file = files.next();
      scannedFiles++;
      if (file.getName().toLowerCase().includes(phrase)) {
        result.push({title: file.getName(), detail: file.getMimeType(),
                     summary: 'Arquivo em pasta autorizada', url: file.getUrl()});
      }
    }
    const children = folder.getFolders();
    while (children.hasNext() && queue.length < 50) queue.push(children.next());
  }
  return result;
}

function create_(operation, payload, folder) {
  const title = String(payload.title || '').trim().slice(0, 180);
  if (!title) throw new Error('Título necessário.');
  let id;
  let url;
  if (operation === 'document.create') {
    const body = String(payload.body || '').trim();
    if (!body || body.length > 12000) throw new Error('Conteúdo inválido.');
    const doc = DocumentApp.create(title);
    doc.getBody().setText(body);
    doc.saveAndClose();
    id = doc.getId();
    url = doc.getUrl();
  } else if (operation === 'spreadsheet.create') {
    const csv = String(payload.csv || '');
    if (!csv.trim() || csv.length > 12000) throw new Error('Dados inválidos.');
    const rows = Utilities.parseCsv(csv);
    if (!rows.length || rows.length > 100 ||
        rows.some(row => !row.length || row.length > 20 ||
                 row.some(value => String(value).length > 500))) throw new Error('Limite de células.');
    const safeRows = rows.map(row => row.map(value => {
      const text = String(value);
      return /^[\s]*[=+\-@]/.test(text) ? "'" + text : text;
    }));
    const cols = Math.max.apply(null, safeRows.map(row => row.length));
    const normalized = safeRows.map(row => row.concat(Array(cols - row.length).fill('')));
    const spreadsheet = SpreadsheetApp.create(title);
    spreadsheet.getSheets()[0].getRange(1, 1, normalized.length, cols).setValues(normalized);
    id = spreadsheet.getId();
    url = spreadsheet.getUrl();
  } else {
    const outline = String(payload.outline || '').trim();
    const parts = outline.split(/\n---\n/).map(part => part.trim()).filter(Boolean);
    if (!outline || outline.length > 10000 || parts.length > 8 || !parts.length) {
      throw new Error('Apresentação inválida.');
    }
    const slides = parts.map(part => {
      const lines = part.split(/\r?\n/);
      const heading = lines.shift().replace(/^#+\s*/, '').trim().slice(0, 110);
      if (!heading) throw new Error('Slide sem título.');
      return [heading, lines.join('\n').trim().slice(0, 1600)];
    });
    const deck = SlidesApp.create(title);
    let first = deck.getSlides()[0];
    if (first) first.getPageElements().forEach(element => element.remove());
    slides.forEach((slideContent, index) => {
      const slide = index === 0 && first ? first :
                    deck.appendSlide(SlidesApp.PredefinedLayout.BLANK);
      const heading = slide.insertTextBox(slideContent[0], 40, 30, 640, 75);
      heading.getText().getTextStyle().setFontSize(30).setBold(true);
      if (slideContent[1]) {
        slide.insertTextBox(slideContent[1], 45, 125, 620, 245)
          .getText().getTextStyle().setFontSize(19);
      }
    });
    id = deck.getId();
    url = deck.getUrl();
  }
  // Never create or move files outside the allowlisted Drive folder.
  DriveApp.getFileById(id).moveTo(folder);
  return {id: id, url: url};
}

/** Run once in the script editor to prompt for Google authorization. */
function autorizarAcesso() {
  const roots = allowedRoots_();
  DriveApp.getFolderById(roots[0]).getName();
}
