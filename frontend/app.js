let currentPage = 1;
const pageSize = 20;
let hasMorePages = true;

async function loadDocuments() {
    try {
        const skip = (currentPage - 1) * pageSize;
        const res = await fetch(`/documents/?skip=${skip}&limit=${pageSize}`);
        const docs = await res.json();
        const docList = document.getElementById('docList');
        
        hasMorePages = docs.length === pageSize;
        
        if (docs.length === 0 && currentPage === 1) {
            docList.innerHTML = '<div class="no-results"><p>暂无文档，请上传新文档</p></div>';
        } else {
            docList.innerHTML = docs.map(doc => `
                <div class="doc-item" data-id="${doc.id}">
                    <div class="doc-item-main">
                        <h3>${escapeHtml(doc.title || '无标题')}</h3>
                        <div class="meta">${escapeHtml(doc.category)} | ${escapeHtml(doc.tags)} | ${new Date(doc.created_at).toLocaleString()}</div>
                    </div>
                    <button class="delete-btn" data-id="${doc.id}">删除</button>
                </div>
            `).join('');
        }
        
        updatePagination();
        
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const docId = parseInt(btn.dataset.id);
                if (confirm('确定要删除这个文档吗？')) {
                    await fetch(`/documents/${docId}`, {method: 'DELETE'});
                    loadDocuments();
                }
            });
        });
    } catch (error) {
        console.error('加载文档失败:', error);
    }
}

function updatePagination() {
    const prevBtn = document.getElementById('prevPage');
    const nextBtn = document.getElementById('nextPage');
    const pageInfo = document.getElementById('pageInfo');
    
    prevBtn.disabled = currentPage === 1;
    nextBtn.disabled = !hasMorePages;
    pageInfo.textContent = `第 ${currentPage} 页`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function highlightText(text, query) {
    if (!query) return escapeHtml(text);
    const regex = new RegExp(`(${escapeHtml(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return escapeHtml(text).replace(regex, '<mark>$1</mark>');
}

async function searchDocuments() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) {
        currentPage = 1;
        loadDocuments();
        document.getElementById('pagination').classList.remove('hidden');
        return;
    }
    
    document.getElementById('pagination').classList.add('hidden');
    
    try {
        const res = await fetch(`/search/?query=${encodeURIComponent(query)}`);
        const docs = await res.json();
        const docList = document.getElementById('docList');
        
        if (docs.length === 0) {
            docList.innerHTML = `
                <div class="no-results">
                    <p>没有找到包含 "${escapeHtml(query)}" 的文档</p>
                </div>
            `;
            return;
        }
        
        docList.innerHTML = docs.map(doc => {
            let matchesHtml = '';
            if (doc.matches && doc.matches.length > 0) {
                matchesHtml = `
                    <div class="matches">
                        <div class="match-count">找到 ${doc.match_count} 处匹配</div>
                        ${doc.matches.slice(0, 3).map(match => `
                            <div class="match-snippet">
                                <span class="context-before">...${highlightText(match.context_before, query)}</span>
                                <span class="matched">${highlightText(match.matched_text, query)}</span>
                                <span class="context-after">${highlightText(match.context_after, query)}...</span>
                            </div>
                        `).join('')}
                        ${doc.matches.length > 3 ? `<div class="more-matches">还有 ${doc.matches.length - 3} 处匹配...</div>` : ''}
                    </div>
                `;
            }
            return `
                <div class="doc-item search-result" data-id="${doc.id}">
                    <div class="doc-item-main">
                        <div class="doc-header">
                            <h3>${escapeHtml(doc.title || '无标题')}</h3>
                            ${doc.is_keyword_match ? '<span class="badge keyword-match">关键词匹配</span>' : ''}
                        </div>
                        <div class="meta">${escapeHtml(doc.category)} | ${escapeHtml(doc.tags)} | ${new Date(doc.created_at).toLocaleString()}</div>
                        ${matchesHtml}
                    </div>
                    <button class="delete-btn" data-id="${doc.id}">删除</button>
                </div>
            `;
        }).join('');
        
        document.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const docId = parseInt(btn.dataset.id);
                if (confirm('确定要删除这个文档吗？')) {
                    await fetch(`/documents/${docId}`, {method: 'DELETE'});
                    searchDocuments();
                }
            });
        });
    } catch (error) {
        console.error('搜索文档失败:', error);
    }
}

function showUploadPanel() {
    document.getElementById('uploadPanel').classList.remove('hidden');
    document.getElementById('docList').classList.add('hidden');
    document.getElementById('pagination').classList.add('hidden');
    resetUploadForm();
}

function hideUploadPanel() {
    document.getElementById('uploadPanel').classList.add('hidden');
    document.getElementById('docList').classList.remove('hidden');
    const query = document.getElementById('searchInput').value.trim();
    if (!query) {
        document.getElementById('pagination').classList.remove('hidden');
    }
}

function resetUploadForm() {
    document.getElementById('docTitle').value = '';
    document.getElementById('docCategory').value = 'history';
    document.getElementById('docTags').value = '';
    document.getElementById('docContent').value = '';
    document.getElementById('docFile').value = '';
}

async function uploadDocument() {
    const title = document.getElementById('docTitle').value.trim();
    if (!title) {
        alert('请输入文档标题');
        return;
    }
    
    const formData = new FormData();
    formData.append('title', title);
    formData.append('category', document.getElementById('docCategory').value);
    formData.append('tags', document.getElementById('docTags').value);
    formData.append('content', document.getElementById('docContent').value);
    
    const fileInput = document.getElementById('docFile');
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }
    
    try {
        await fetch('/documents/', {
            method: 'POST',
            body: formData
        });
        
        hideUploadPanel();
        currentPage = 1;
        loadDocuments();
    } catch (error) {
        console.error('上传文档失败:', error);
        alert('上传文档失败，请重试');
    }
}

// Event listeners
document.getElementById('newDocBtn').addEventListener('click', showUploadPanel);
document.getElementById('uploadDocBtn').addEventListener('click', uploadDocument);
document.getElementById('cancelBtn').addEventListener('click', hideUploadPanel);
document.getElementById('searchBtn').addEventListener('click', searchDocuments);
document.getElementById('searchInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') searchDocuments();
});

document.getElementById('prevPage').addEventListener('click', () => {
    if (currentPage > 1) {
        currentPage--;
        loadDocuments();
    }
});

document.getElementById('nextPage').addEventListener('click', () => {
    if (hasMorePages) {
        currentPage++;
        loadDocuments();
    }
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
