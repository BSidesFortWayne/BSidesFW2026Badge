// In-browser Monaco editor for the badge simulator.
//
// Layout: collapsible file tree on the left, Monaco on the right.
// Storage (all in localStorage, no backend):
//   badge_sim_edit:<path>     — content of EDITED src/ files
//   badge_sim_created:<path>  — content of NEW files (not in the original src/ tree)
//   badge_sim_deleted         — JSON array of tombstoned src/ paths
//   badge_sim_folders         — JSON array of empty folders the user created
//   badge_sim_last_path       — last-opened file (restored on reload)
//   badge_sim_expanded        — JSON array of expanded folder paths

const MONACO_CDN = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs';
const KEY_EDIT = 'badge_sim_edit:';
const KEY_CREATED = 'badge_sim_created:';
const KEY_DELETED = 'badge_sim_deleted';
const KEY_FOLDERS = 'badge_sim_folders';
const KEY_LAST = 'badge_sim_last_path';
const KEY_EXPANDED = 'badge_sim_expanded';

// Set of file paths that exist in the on-disk src/ tree (populated from
// build/src_index.json). Used to distinguish "edit existing" vs "create new".
let srcFiles = new Set();

// In-memory cache of original contents fetched from build/src/<path>.
// path -> string. Lazily populated.
const originalCache = new Map();

let monacoEditor = null;
let activePath = null;   // file currently shown in Monaco
let selectedPath = null; // last-clicked tree row (file or folder); '' = root
let expandedFolders = new Set();
let logFn = (msg, level) => console.log(`[editor:${level || 'INFO'}] ${msg}`);

// DOM refs (populated by setupUiRefs)
let dirtyDot, activePathEl, reloadBtn, downloadBtn, revertBtn, treeEl;

export async function initEditor({ addLog } = {}) {
    if (addLog) logFn = addLog;

    setupUiRefs();
    loadExpandedFromStorage();

    const [, ] = await Promise.all([
        fetchSrcIndex(),
        loadMonacoLoader(),
    ]);

    // Default-expand top-level folders so the tree isn't a single line.
    if (expandedFolders.size === 0) {
        const tops = new Set();
        for (const p of listAllFiles()) {
            if (p.includes('/')) tops.add(p.split('/')[0]);
        }
        expandedFolders = tops;
        saveExpandedToStorage();
    }

    renderTree();

    await new Promise((resolve, reject) => {
        // eslint-disable-next-line no-undef
        require.config({ paths: { vs: MONACO_CDN } });
        // eslint-disable-next-line no-undef
        require(['vs/editor/editor.main'], () => {
            try {
                createMonaco();
                resolve();
            } catch (e) {
                reject(e);
            }
        }, reject);
    });

    // Restore previously-open file if it still exists.
    const last = localStorage.getItem(KEY_LAST);
    if (last && fileExists(last)) {
        await openFile(last);
    } else {
        const all = listAllFiles();
        if (all.length > 0) await openFile(all[0]);
    }

    logFn('Editor ready', 'INFO');
}

// ── DOM setup ─────────────────────────────────────────────────────────────

function setupUiRefs() {
    activePathEl = document.getElementById('editor-active-path');
    reloadBtn = document.getElementById('editor-reload');
    downloadBtn = document.getElementById('editor-download');
    revertBtn = document.getElementById('editor-revert');
    dirtyDot = document.getElementById('editor-dirty');
    treeEl = document.getElementById('editor-tree');

    const fullReloadBtn = document.getElementById('editor-full-reload');
    const toggleBtn = document.getElementById('editor-toggle');
    const editorPanel = document.getElementById('editor-panel');
    if (toggleBtn && editorPanel) {
        toggleBtn.addEventListener('click', () => {
            editorPanel.classList.toggle('collapsed');
            toggleBtn.textContent = editorPanel.classList.contains('collapsed')
                ? 'Expand' : 'Collapse';
            if (monacoEditor && !editorPanel.classList.contains('collapsed')) {
                setTimeout(() => monacoEditor.layout(), 50);
            }
        });
    }

    if (reloadBtn) reloadBtn.addEventListener('click', onReloadApp);
    if (fullReloadBtn) {
        fullReloadBtn.addEventListener('click', () => {
            if (window.editorBridge && window.editorBridge.fullReload) {
                window.editorBridge.fullReload();
            } else {
                window.location.reload();
            }
        });
    }
    if (downloadBtn) downloadBtn.addEventListener('click', onDownload);
    if (revertBtn) revertBtn.addEventListener('click', onRevert);

    const newFileBtn = document.getElementById('editor-new-file');
    const newFolderBtn = document.getElementById('editor-new-folder');
    const collapseAllBtn = document.getElementById('editor-collapse-all');
    if (newFileBtn) newFileBtn.addEventListener('click', () => onNewFile());
    if (newFolderBtn) newFolderBtn.addEventListener('click', () => onNewFolder());
    if (collapseAllBtn) collapseAllBtn.addEventListener('click', () => {
        expandedFolders.clear();
        saveExpandedToStorage();
        renderTree();
    });

    setupResizeHandle();
    setupSidebarResize();
    setupTreeDragDrop();
}

function setupResizeHandle() {
    const handle = document.getElementById('editor-resize-handle');
    const panel = document.getElementById('editor-panel');
    if (!handle || !panel) return;
    let resizing = false, startY = 0, startHeight = 0;
    handle.addEventListener('mousedown', (e) => {
        resizing = true;
        startY = e.clientY;
        startHeight = panel.offsetHeight;
        document.body.style.cursor = 'ns-resize';
        e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
        if (!resizing) return;
        const delta = startY - e.clientY;
        const newHeight = Math.max(120, Math.min(window.innerHeight * 0.85,
            startHeight + delta));
        panel.style.flex = `0 0 ${newHeight}px`;
        panel.classList.remove('collapsed');
        const toggleBtn = document.getElementById('editor-toggle');
        if (toggleBtn) toggleBtn.textContent = 'Collapse';
        if (monacoEditor) monacoEditor.layout();
    });
    document.addEventListener('mouseup', () => {
        if (resizing) { resizing = false; document.body.style.cursor = ''; }
    });
}

function setupSidebarResize() {
    const handle = document.getElementById('editor-sidebar-resize');
    const sidebar = document.getElementById('editor-sidebar');
    if (!handle || !sidebar) return;
    let resizing = false, startX = 0, startW = 0;
    handle.addEventListener('mousedown', (e) => {
        resizing = true;
        startX = e.clientX;
        startW = sidebar.offsetWidth;
        document.body.style.cursor = 'ew-resize';
        e.preventDefault();
    });
    document.addEventListener('mousemove', (e) => {
        if (!resizing) return;
        const delta = e.clientX - startX;
        const newW = Math.max(120, startW + delta);
        sidebar.style.flex = `0 0 ${newW}px`;
        if (monacoEditor) monacoEditor.layout();
    });
    document.addEventListener('mouseup', () => {
        if (resizing) { resizing = false; document.body.style.cursor = ''; }
    });
}

// ── Storage model ─────────────────────────────────────────────────────────

function getDeleted() {
    try {
        return new Set(JSON.parse(localStorage.getItem(KEY_DELETED) || '[]'));
    } catch (_) { return new Set(); }
}

function setDeleted(set) {
    localStorage.setItem(KEY_DELETED, JSON.stringify([...set].sort()));
}

function getFolders() {
    try {
        return new Set(JSON.parse(localStorage.getItem(KEY_FOLDERS) || '[]'));
    } catch (_) { return new Set(); }
}

function setFolders(set) {
    localStorage.setItem(KEY_FOLDERS, JSON.stringify([...set].sort()));
}

function loadExpandedFromStorage() {
    try {
        expandedFolders = new Set(JSON.parse(localStorage.getItem(KEY_EXPANDED) || '[]'));
    } catch (_) { expandedFolders = new Set(); }
}

function saveExpandedToStorage() {
    localStorage.setItem(KEY_EXPANDED, JSON.stringify([...expandedFolders].sort()));
}

function listAllFiles() {
    const deleted = getDeleted();
    const result = new Set();
    for (const p of srcFiles) if (!deleted.has(p)) result.add(p);
    // Created files (any localStorage key with KEY_CREATED prefix).
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        if (k && k.startsWith(KEY_CREATED)) result.add(k.slice(KEY_CREATED.length));
    }
    return [...result].sort();
}

function fileExists(path) {
    if (localStorage.getItem(KEY_CREATED + path) !== null) return true;
    if (srcFiles.has(path) && !getDeleted().has(path)) return true;
    return false;
}

// Read current content of `path`:
//   1. If edited (KEY_EDIT) → that. (existing edits to src files)
//   2. Else if created (KEY_CREATED) → that. (new files)
//   3. Else fetch from build/src/<path>.
async function loadContent(path) {
    const edited = localStorage.getItem(KEY_EDIT + path);
    if (edited !== null) return edited;
    const created = localStorage.getItem(KEY_CREATED + path);
    if (created !== null) return created;
    if (originalCache.has(path)) return originalCache.get(path);
    try {
        const r = await fetch(`build/src/${path}`, { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const text = await r.text();
        originalCache.set(path, text);
        return text;
    } catch (e) {
        logFn(`Cannot read ${path}: ${e.message}`, 'WARNING');
        return '';
    }
}

// Get the on-disk-original (for revert / dirty comparison). null if no original.
async function loadOriginal(path) {
    if (!srcFiles.has(path) || getDeleted().has(path)) return null;
    if (originalCache.has(path)) return originalCache.get(path);
    try {
        const r = await fetch(`build/src/${path}`, { cache: 'no-store' });
        if (!r.ok) return null;
        const text = await r.text();
        originalCache.set(path, text);
        return text;
    } catch (_) { return null; }
}

function saveContent(path, content) {
    if (srcFiles.has(path) && !getDeleted().has(path)) {
        // Edit of original src file.
        const original = originalCache.get(path);
        if (original !== undefined && content === original) {
            localStorage.removeItem(KEY_EDIT + path);
        } else {
            localStorage.setItem(KEY_EDIT + path, content);
        }
    } else {
        // Created file (no original to diff against).
        localStorage.setItem(KEY_CREATED + path, content);
    }
}

function validatePath(path) {
    if (!path || typeof path !== 'string') return 'Empty path';
    if (path.startsWith('/') || path.endsWith('/')) return 'Path must not start or end with /';
    if (path.includes('//')) return 'Path must not contain //';
    if (!/^[A-Za-z0-9_./-]+$/.test(path)) return 'Path may only contain A-Z a-z 0-9 _ . / -';
    if (path.split('/').some(s => s === '' || s === '.' || s === '..')) return 'Invalid path segment';
    return null;
}

function createFile(path, content = '') {
    const err = validatePath(path);
    if (err) { logFn(`Create failed: ${err}`, 'WARNING'); return false; }
    if (fileExists(path)) {
        logFn(`Create failed: ${path} already exists`, 'WARNING');
        return false;
    }
    // Un-tombstone if creating a path that matches a deleted src file —
    // effectively undelete + overwrite.
    const deleted = getDeleted();
    if (deleted.has(path)) {
        deleted.delete(path);
        setDeleted(deleted);
    }
    if (srcFiles.has(path)) {
        localStorage.setItem(KEY_EDIT + path, content);
    } else {
        localStorage.setItem(KEY_CREATED + path, content);
    }
    return true;
}

function createFolder(path) {
    const err = validatePath(path);
    if (err) { logFn(`Create folder failed: ${err}`, 'WARNING'); return false; }
    const folders = getFolders();
    folders.add(path);
    setFolders(folders);
    expandedFolders.add(path);
    // Also expand all ancestors so the new folder is visible.
    const parts = path.split('/');
    for (let i = 1; i < parts.length; i++) {
        expandedFolders.add(parts.slice(0, i).join('/'));
    }
    saveExpandedToStorage();
    return true;
}

function deletePath(path, { recursive = false } = {}) {
    // If it's a file, just delete it.
    if (fileExists(path)) {
        if (srcFiles.has(path)) {
            const deleted = getDeleted();
            deleted.add(path);
            setDeleted(deleted);
        }
        localStorage.removeItem(KEY_EDIT + path);
        localStorage.removeItem(KEY_CREATED + path);
        return true;
    }
    // Otherwise treat as a folder.
    const prefix = path + '/';
    const filesUnder = listAllFiles().filter(p => p.startsWith(prefix));
    if (filesUnder.length > 0) {
        if (!recursive) {
            logFn(`Folder ${path} not empty (${filesUnder.length} files). Confirm to delete recursively.`, 'WARNING');
            return false;
        }
        for (const f of filesUnder) deletePath(f);
    }
    // Remove the explicit-folder entry if present.
    const folders = getFolders();
    if (folders.has(path)) {
        folders.delete(path);
        setFolders(folders);
    }
    expandedFolders.delete(path);
    saveExpandedToStorage();
    return true;
}

async function renamePath(oldPath, newPath) {
    if (oldPath === newPath) return true;
    const err = validatePath(newPath);
    if (err) { logFn(`Rename failed: ${err}`, 'WARNING'); return false; }
    if (fileExists(newPath)) {
        logFn(`Rename failed: ${newPath} already exists`, 'WARNING');
        return false;
    }
    // File rename
    if (fileExists(oldPath)) {
        const content = await loadContent(oldPath);
        if (!createFile(newPath, content)) return false;
        deletePath(oldPath);
        return true;
    }
    // Folder rename: move every file under oldPath/ → newPath/
    const prefix = oldPath + '/';
    const filesUnder = listAllFiles().filter(p => p.startsWith(prefix));
    for (const f of filesUnder) {
        const sub = f.slice(prefix.length);
        const target = newPath + '/' + sub;
        const content = await loadContent(f);
        if (!createFile(target, content)) {
            logFn(`Rename partial: failed at ${target}`, 'WARNING');
            return false;
        }
        deletePath(f);
    }
    // Move folder entry if explicit
    const folders = getFolders();
    if (folders.has(oldPath)) {
        folders.delete(oldPath);
        folders.add(newPath);
        setFolders(folders);
    }
    // Carry expanded state.
    if (expandedFolders.has(oldPath)) {
        expandedFolders.delete(oldPath);
        expandedFolders.add(newPath);
        saveExpandedToStorage();
    }
    return true;
}

async function duplicateFile(oldPath, newPath) {
    const err = validatePath(newPath);
    if (err) { logFn(`Duplicate failed: ${err}`, 'WARNING'); return false; }
    if (fileExists(newPath)) {
        logFn(`Duplicate failed: ${newPath} already exists`, 'WARNING');
        return false;
    }
    const content = await loadContent(oldPath);
    return createFile(newPath, content);
}

// ── Tree rendering ────────────────────────────────────────────────────────

function buildTree() {
    // Combine files + explicit empty folders into a sorted nested structure.
    // Node: { name, fullPath, isFolder, children: Map<name, Node> }
    const root = { name: '', fullPath: '', isFolder: true, children: new Map() };
    function ensureFolder(parts) {
        let node = root;
        let cur = '';
        for (const part of parts) {
            cur = cur ? cur + '/' + part : part;
            let child = node.children.get(part);
            if (!child) {
                child = { name: part, fullPath: cur, isFolder: true, children: new Map() };
                node.children.set(part, child);
            }
            node = child;
        }
        return node;
    }
    for (const p of listAllFiles()) {
        const parts = p.split('/');
        const file = parts.pop();
        const folder = parts.length > 0 ? ensureFolder(parts) : root;
        folder.children.set(file, {
            name: file, fullPath: p, isFolder: false, children: null,
        });
    }
    for (const f of getFolders()) {
        ensureFolder(f.split('/'));
    }
    return root;
}

function renderTree() {
    if (!treeEl) return;
    const focusBefore = document.activeElement;
    treeEl.innerHTML = '';
    const root = buildTree();
    renderNodeChildren(root, 0);

    // Restore focus if we destroyed it on a rename input
    if (focusBefore && focusBefore.classList && focusBefore.classList.contains('tree-rename-input')) {
        // intentionally not re-focused on full re-render
    }
}

function renderNodeChildren(node, depth) {
    // Folders first, then files, both alphabetized.
    const folders = [];
    const files = [];
    for (const child of node.children.values()) {
        (child.isFolder ? folders : files).push(child);
    }
    folders.sort((a, b) => a.name.localeCompare(b.name));
    files.sort((a, b) => a.name.localeCompare(b.name));

    for (const f of folders) {
        treeEl.appendChild(renderFolderRow(f, depth));
        if (expandedFolders.has(f.fullPath)) {
            renderNodeChildren(f, depth + 1);
        }
    }
    for (const f of files) {
        treeEl.appendChild(renderFileRow(f, depth));
    }
}

function renderFolderRow(node, depth) {
    const row = document.createElement('div');
    row.className = 'tree-row is-folder';
    row.dataset.path = node.fullPath;
    row.dataset.kind = 'folder';
    row.draggable = true;
    if (selectedPath === node.fullPath) row.classList.add('is-selected');

    row.appendChild(indentEl(depth));

    const caret = document.createElement('span');
    caret.className = 'tree-caret';
    caret.textContent = expandedFolders.has(node.fullPath) ? '▾' : '▸';
    row.appendChild(caret);

    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = expandedFolders.has(node.fullPath) ? '📂' : '📁';
    row.appendChild(icon);

    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.name;
    row.appendChild(label);

    row.appendChild(folderActions(node));

    row.addEventListener('click', (e) => {
        if (e.target.closest('.tree-actions')) return;
        selectedPath = node.fullPath;
        if (expandedFolders.has(node.fullPath)) expandedFolders.delete(node.fullPath);
        else expandedFolders.add(node.fullPath);
        saveExpandedToStorage();
        renderTree();
    });

    return row;
}

function renderFileRow(node, depth) {
    const row = document.createElement('div');
    row.className = 'tree-row is-file';
    row.dataset.path = node.fullPath;
    row.dataset.kind = 'file';
    row.draggable = true;

    if (activePath === node.fullPath) row.classList.add('is-active');
    else if (selectedPath === node.fullPath) row.classList.add('is-selected');

    if (localStorage.getItem(KEY_CREATED + node.fullPath) !== null) {
        row.classList.add('is-created');
    } else if (localStorage.getItem(KEY_EDIT + node.fullPath) !== null) {
        row.classList.add('is-edited');
    }

    row.appendChild(indentEl(depth));

    // Spacer where caret would be on folder rows.
    const spacer = document.createElement('span');
    spacer.className = 'tree-caret';
    spacer.textContent = '';
    row.appendChild(spacer);

    const icon = document.createElement('span');
    icon.className = 'tree-icon';
    icon.textContent = node.name.endsWith('.py') ? '🐍' : '📄';
    row.appendChild(icon);

    const label = document.createElement('span');
    label.className = 'tree-label';
    label.textContent = node.name;
    row.appendChild(label);

    row.appendChild(fileActions(node));

    row.addEventListener('click', (e) => {
        if (e.target.closest('.tree-actions')) return;
        selectedPath = node.fullPath;
        openFile(node.fullPath);
    });

    return row;
}

function indentEl(depth) {
    const el = document.createElement('span');
    el.className = 'tree-indent';
    el.style.width = (depth * 12) + 'px';
    return el;
}

function fileActions(node) {
    const wrap = document.createElement('span');
    wrap.className = 'tree-actions';
    wrap.appendChild(makeActionBtn('✎', 'Rename', (e) => {
        e.stopPropagation();
        beginInlineRename(node);
    }));
    wrap.appendChild(makeActionBtn('⧉', 'Duplicate', async (e) => {
        e.stopPropagation();
        await onDuplicateFile(node.fullPath);
    }));
    wrap.appendChild(makeActionBtn('✕', 'Delete', (e) => {
        e.stopPropagation();
        onDeleteFile(node.fullPath);
    }, true));
    return wrap;
}

function folderActions(node) {
    const wrap = document.createElement('span');
    wrap.className = 'tree-actions';
    wrap.appendChild(makeActionBtn('+', 'New file in folder', (e) => {
        e.stopPropagation();
        onNewFile(node.fullPath);
    }));
    wrap.appendChild(makeActionBtn('✎', 'Rename folder', (e) => {
        e.stopPropagation();
        beginInlineRename(node);
    }));
    wrap.appendChild(makeActionBtn('✕', 'Delete folder (recursive)', (e) => {
        e.stopPropagation();
        onDeleteFolder(node.fullPath);
    }, true));
    return wrap;
}

function makeActionBtn(text, title, onClick, danger = false) {
    const b = document.createElement('button');
    b.textContent = text;
    b.title = title;
    if (danger) b.className = 'danger';
    b.addEventListener('click', onClick);
    return b;
}

function beginInlineRename(node) {
    const row = treeEl.querySelector(`.tree-row[data-path="${cssEscape(node.fullPath)}"]`);
    if (!row) return;
    const label = row.querySelector('.tree-label');
    if (!label) return;
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'tree-rename-input';
    input.value = node.name;
    label.replaceWith(input);
    input.focus();
    input.select();
    let done = false;
    const commit = async (apply) => {
        if (done) return;
        done = true;
        if (!apply) { renderTree(); return; }
        const newName = input.value.trim();
        if (!newName || newName === node.name) { renderTree(); return; }
        const parentParts = node.fullPath.split('/');
        parentParts.pop();
        const newPath = (parentParts.length ? parentParts.join('/') + '/' : '') + newName;
        const ok = await renamePath(node.fullPath, newPath);
        if (ok) {
            logFn(`Renamed ${node.fullPath} → ${newPath}`, 'INFO');
            if (activePath === node.fullPath) {
                activePath = newPath;
                localStorage.setItem(KEY_LAST, newPath);
                if (activePathEl) activePathEl.textContent = newPath;
            }
            if (selectedPath === node.fullPath) selectedPath = newPath;
        }
        renderTree();
    };
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); commit(true); }
        else if (e.key === 'Escape') { e.preventDefault(); commit(false); }
    });
    input.addEventListener('blur', () => commit(true));
}

function cssEscape(s) {
    if (window.CSS && CSS.escape) return CSS.escape(s);
    return s.replace(/(["\\])/g, '\\$1');
}

// ── Toolbar / row action handlers ─────────────────────────────────────────

async function onNewFile(parentFolder) {
    // Default parent: explicitly passed folder > selected path > active file's folder > root.
    let defaultParent = '';
    if (parentFolder !== undefined && parentFolder !== null) defaultParent = parentFolder;
    else if (selectedPath && isFolderPath(selectedPath)) defaultParent = selectedPath;
    else if (selectedPath && fileExists(selectedPath)) {
        const parts = selectedPath.split('/'); parts.pop();
        defaultParent = parts.join('/');
    } else if (activePath) {
        const parts = activePath.split('/'); parts.pop();
        defaultParent = parts.join('/');
    }
    const prefill = defaultParent ? defaultParent + '/' : '';
    const input = window.prompt('New file path (relative to src/):', prefill);
    if (!input) return;
    const path = input.trim();
    if (!path) return;
    if (createFile(path, '')) {
        // Expand ancestor folders so the new file is visible.
        const parts = path.split('/');
        for (let i = 1; i < parts.length; i++) {
            expandedFolders.add(parts.slice(0, i).join('/'));
        }
        saveExpandedToStorage();
        renderTree();
        await openFile(path);
        logFn(`Created ${path}`, 'INFO');
    }
}

async function onNewFolder() {
    let defaultParent = '';
    if (selectedPath && isFolderPath(selectedPath)) defaultParent = selectedPath;
    const prefill = defaultParent ? defaultParent + '/' : '';
    const input = window.prompt('New folder path:', prefill);
    if (!input) return;
    const path = input.trim().replace(/\/$/, '');
    if (!path) return;
    if (createFolder(path)) {
        renderTree();
        logFn(`Created folder ${path}`, 'INFO');
    }
}

async function onDuplicateFile(path) {
    const suggested = path.replace(/(\.[^./]+)?$/, (m) => '.copy' + (m || ''));
    const input = window.prompt('Duplicate to path:', suggested);
    if (!input) return;
    const newPath = input.trim();
    if (!newPath) return;
    if (await duplicateFile(path, newPath)) {
        renderTree();
        await openFile(newPath);
        logFn(`Duplicated ${path} → ${newPath}`, 'INFO');
    }
}

function onDeleteFile(path) {
    if (!window.confirm(`Delete ${path}?`)) return;
    if (deletePath(path)) {
        if (activePath === path) {
            activePath = null;
            if (monacoEditor) monacoEditor.setValue('');
            if (activePathEl) activePathEl.textContent = '';
            localStorage.removeItem(KEY_LAST);
        }
        renderTree();
        logFn(`Deleted ${path}`, 'INFO');
    }
}

function onDeleteFolder(path) {
    const prefix = path + '/';
    const filesUnder = listAllFiles().filter(p => p.startsWith(prefix));
    const msg = filesUnder.length
        ? `Delete folder ${path} and ${filesUnder.length} files in it?`
        : `Delete empty folder ${path}?`;
    if (!window.confirm(msg)) return;
    if (deletePath(path, { recursive: true })) {
        if (activePath && activePath.startsWith(prefix)) {
            activePath = null;
            if (monacoEditor) monacoEditor.setValue('');
            if (activePathEl) activePathEl.textContent = '';
            localStorage.removeItem(KEY_LAST);
        }
        renderTree();
        logFn(`Deleted folder ${path}`, 'INFO');
    }
}

function isFolderPath(p) {
    if (!p) return true; // root
    if (getFolders().has(p)) return true;
    const prefix = p + '/';
    for (const f of listAllFiles()) if (f.startsWith(prefix)) return true;
    return false;
}

// ── Drag & drop (move within tree) ────────────────────────────────────────

function setupTreeDragDrop() {
    if (!treeEl) return;
    let dragSrc = null;

    treeEl.addEventListener('dragstart', (e) => {
        const row = e.target.closest('.tree-row');
        if (!row) return;
        dragSrc = { path: row.dataset.path, kind: row.dataset.kind };
        e.dataTransfer.effectAllowed = 'move';
        try { e.dataTransfer.setData('text/plain', row.dataset.path); } catch (_) {}
    });

    treeEl.addEventListener('dragover', (e) => {
        if (!dragSrc) return;
        const row = e.target.closest('.tree-row');
        if (!row) {
            // dropping on empty area = root
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            treeEl.querySelectorAll('.is-drop-target').forEach(el => el.classList.remove('is-drop-target'));
            return;
        }
        const targetFolder = row.dataset.kind === 'folder' ? row.dataset.path : parentOf(row.dataset.path);
        if (canDrop(dragSrc, targetFolder)) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            treeEl.querySelectorAll('.is-drop-target').forEach(el => el.classList.remove('is-drop-target'));
            row.classList.add('is-drop-target');
        }
    });

    treeEl.addEventListener('dragleave', (e) => {
        const row = e.target.closest('.tree-row');
        if (row) row.classList.remove('is-drop-target');
    });

    treeEl.addEventListener('drop', async (e) => {
        treeEl.querySelectorAll('.is-drop-target').forEach(el => el.classList.remove('is-drop-target'));
        if (!dragSrc) return;
        e.preventDefault();
        const row = e.target.closest('.tree-row');
        const targetFolder = row
            ? (row.dataset.kind === 'folder' ? row.dataset.path : parentOf(row.dataset.path))
            : '';
        if (!canDrop(dragSrc, targetFolder)) { dragSrc = null; return; }
        const name = dragSrc.path.split('/').pop();
        const newPath = targetFolder ? targetFolder + '/' + name : name;
        if (newPath === dragSrc.path) { dragSrc = null; return; }
        const wasActive = activePath === dragSrc.path;
        const ok = await renamePath(dragSrc.path, newPath);
        if (ok) {
            logFn(`Moved ${dragSrc.path} → ${newPath}`, 'INFO');
            if (wasActive) {
                activePath = newPath;
                localStorage.setItem(KEY_LAST, newPath);
                if (activePathEl) activePathEl.textContent = newPath;
            }
            renderTree();
        }
        dragSrc = null;
    });
}

function parentOf(path) {
    const i = path.lastIndexOf('/');
    return i < 0 ? '' : path.slice(0, i);
}

function canDrop(src, targetFolder) {
    if (src.path === targetFolder) return false;
    if (src.kind === 'folder') {
        // can't drop a folder into itself or a descendant
        if (targetFolder === src.path) return false;
        if (targetFolder.startsWith(src.path + '/')) return false;
    }
    // landing in the same folder is a no-op
    if (parentOf(src.path) === targetFolder) return false;
    return true;
}

// ── Monaco / buffer ───────────────────────────────────────────────────────

function createMonaco() {
    const host = document.getElementById('editor-host');
    if (!host) throw new Error('#editor-host missing');
    // eslint-disable-next-line no-undef
    monacoEditor = monaco.editor.create(host, {
        value: '# Select a file to begin editing',
        language: 'python',
        theme: 'vs-dark',
        automaticLayout: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 12,
        tabSize: 4,
        insertSpaces: true,
    });
    monacoEditor.onDidChangeModelContent(() => {
        if (!activePath) return;
        saveContent(activePath, monacoEditor.getValue());
        scheduleDirtyRefresh();
    });
}

let dirtyTimer = null;
function scheduleDirtyRefresh() {
    if (dirtyTimer) clearTimeout(dirtyTimer);
    dirtyTimer = setTimeout(async () => {
        await updateDirtyIndicator();
        // Re-tag the file row's class without a full re-render.
        if (!activePath) return;
        const row = treeEl.querySelector(`.tree-row[data-path="${cssEscape(activePath)}"]`);
        if (row) {
            row.classList.toggle('is-created',
                localStorage.getItem(KEY_CREATED + activePath) !== null);
            row.classList.toggle('is-edited',
                localStorage.getItem(KEY_EDIT + activePath) !== null);
        }
    }, 300);
}

async function openFile(path) {
    if (!path) return;
    if (!fileExists(path)) {
        logFn(`Cannot open ${path}: does not exist`, 'WARNING');
        return;
    }
    activePath = path;
    selectedPath = path;
    localStorage.setItem(KEY_LAST, path);
    if (activePathEl) activePathEl.textContent = path;

    const content = await loadContent(path);
    if (monacoEditor) {
        // eslint-disable-next-line no-undef
        monacoEditor.setValue(content);
    }
    await updateDirtyIndicator();

    // Update active highlight in tree without rebuilding.
    treeEl.querySelectorAll('.tree-row.is-active').forEach(el => el.classList.remove('is-active'));
    treeEl.querySelectorAll('.tree-row.is-selected').forEach(el => el.classList.remove('is-selected'));
    const row = treeEl.querySelector(`.tree-row[data-path="${cssEscape(path)}"]`);
    if (row) row.classList.add('is-active');
}

async function updateDirtyIndicator() {
    if (!dirtyDot) return;
    if (!activePath) { dirtyDot.classList.remove('active'); return; }
    const original = await loadOriginal(activePath);
    let dirty = false;
    if (original !== null) {
        const cur = localStorage.getItem(KEY_EDIT + activePath);
        if (cur !== null && cur !== original) dirty = true;
    } else {
        // Created file is always "dirty" relative to nothing.
        dirty = localStorage.getItem(KEY_CREATED + activePath) !== null;
    }
    dirtyDot.classList.toggle('active', dirty);
    dirtyDot.title = dirty ? 'Unsaved changes (localStorage only)' : 'No unsaved changes';
}

// ── Reload / Download / Revert ────────────────────────────────────────────

function pathToModule(path) {
    if (!path.endsWith('.py')) return null;
    let m = path.slice(0, -3);
    if (m.endsWith('/__init__') || m === '__init__') return null;
    return m.replace(/\//g, '.');
}

async function onReloadApp() {
    if (!activePath) return;
    const modulePath = pathToModule(activePath);
    if (!modulePath) {
        logFn(`Can't hot-swap ${activePath} — use Full Reload`, 'WARNING');
        return;
    }
    if (!window.editorBridge || !window.editorBridge.applyOverlay) {
        logFn('Editor bridge not ready yet (waiting for MicroPython boot)', 'WARNING');
        return;
    }
    const source = await loadContent(activePath);
    reloadBtn.disabled = true;
    try {
        await window.editorBridge.applyOverlay(modulePath, source);
    } finally {
        reloadBtn.disabled = false;
    }
}

async function onDownload() {
    if (!activePath) return;
    const content = await loadContent(activePath);
    const filename = activePath.replace(/\//g, '_');
    const blob = new Blob([content], { type: 'text/x-python' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 500);
}

async function onRevert() {
    if (!activePath) return;
    const original = await loadOriginal(activePath);
    if (original === null) {
        logFn(`Revert: no original on disk for ${activePath}`, 'WARNING');
        return;
    }
    localStorage.removeItem(KEY_EDIT + activePath);
    if (monacoEditor) {
        // eslint-disable-next-line no-undef
        monacoEditor.setValue(original);
    }
    await updateDirtyIndicator();
    renderTree();
}

// ── Index / Monaco loader ─────────────────────────────────────────────────

async function fetchSrcIndex() {
    try {
        const r = await fetch('build/src_index.json', { cache: 'no-store' });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const data = await r.json();
        srcFiles = new Set(data.files || []);
    } catch (e) {
        logFn(`Editor: cannot load src_index.json (${e.message}). Rebuild the WASM.`, 'WARNING');
        srcFiles = new Set();
    }
}

function loadMonacoLoader() {
    return new Promise((resolve, reject) => {
        if (window.require && window.require.config) return resolve();
        const script = document.createElement('script');
        script.src = `${MONACO_CDN}/loader.js`;
        script.onload = () => resolve();
        script.onerror = () => reject(new Error('Monaco loader fetch failed'));
        document.head.appendChild(script);
    });
}
