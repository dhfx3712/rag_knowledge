let currentDocId = null;

async function loadDocuments() {
    const res = await fetch('/documents/');
    const docs = await res.json();
    const docList = document.getElementById('docList');
    docList.innerHTML = docs.map(doc => `
        <div class="doc-item" data-id="${doc.id}">
            <h3>${doc.title}</h3>
            <div class="meta">${doc.category} | ${doc.tags} | ${new Date(doc.created_at).toLocaleString()}</div>
        </div>
    `).join('');
    
    document.querySelectorAll('.doc-item').forEach(item => {
        item.addEventListener('click', () => editDocument(parseInt(item.dataset.id)));
    });
}

async function editDocument(docId) {
    currentDocId = docId;
    const res = await fetch(`/documents/${docId}`);
    const doc = await res.json();
    
    document.getElementById('docTitle').value = doc.title;
    document.getElementById('docCategory').value = doc.category;
    document.getElementById('docTags').value = doc.tags;
    document.getElementById('docContent').value = doc.content;
    document.getElementById('docFile').value = ''; // Clear file input
    
    document.getElementById('docEditor').classList.remove('hidden');
    document.getElementById('deleteDocBtn').classList.remove('hidden');
}

function newDocument() {
    currentDocId = null;
    document.getElementById('docTitle').value = '';
    document.getElementById('docCategory').value = 'history';
    document.getElementById('docTags').value = '';
    document.getElementById('docContent').value = '';
    document.getElementById('docFile').value = '';
    
    document.getElementById('docEditor').classList.remove('hidden');
    document.getElementById('deleteDocBtn').classList.add('hidden');
}

async function saveDocument() {
    const formData = new FormData();
    formData.append('title', document.getElementById('docTitle').value);
    formData.append('category', document.getElementById('docCategory').value);
    formData.append('tags', document.getElementById('docTags').value);
    formData.append('content', document.getElementById('docContent').value);
    
    const fileInput = document.getElementById('docFile');
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }
    
    const url = currentDocId ? `/documents/${currentDocId}` : '/documents/';
    const method = currentDocId ? 'PUT' : 'POST';
    
    await fetch(url, {
        method: method,
        body: formData
    });
    
    document.getElementById('docEditor').classList.add('hidden');
    loadDocuments();
}

async function deleteDocument() {
    if (!confirm('确定要删除这个文档吗？')) return;
    await fetch(`/documents/${currentDocId}`, {method: 'DELETE'});
    document.getElementById('docEditor').classList.add('hidden');
    loadDocuments();
}

async function searchDocuments() {
    const query = document.getElementById('searchInput').value;
    if (!query) {
        loadDocuments();
        return;
    }
    const res = await fetch(`/search/?query=${encodeURIComponent(query)}`);
    const docs = await res.json();
    const docList = document.getElementById('docList');
    docList.innerHTML = docs.map(doc => `
        <div class="doc-item" data-id="${doc.id}">
            <h3>${doc.title}</h3>
            <div class="meta">${doc.category} | ${doc.tags} | ${new Date(doc.created_at).toLocaleString()}</div>
        </div>
    `).join('');
    
    document.querySelectorAll('.doc-item').forEach(item => {
        item.addEventListener('click', () => editDocument(parseInt(item.dataset.id)));
    });
}

// Event listeners
document.getElementById('newDocBtn').addEventListener('click', newDocument);
document.getElementById('saveDocBtn').addEventListener('click', saveDocument);
document.getElementById('cancelBtn').addEventListener('click', () => {
    document.getElementById('docEditor').classList.add('hidden');
});
document.getElementById('deleteDocBtn').addEventListener('click', deleteDocument);
document.getElementById('searchBtn').addEventListener('click', searchDocuments);
document.getElementById('searchInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchDocuments();
});

// Load file content into textarea when file is selected
document.getElementById('docFile').addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (file) {
        const text = await file.text();
        document.getElementById('docContent').value = text;
    }
});

// Initial load
loadDocuments();
