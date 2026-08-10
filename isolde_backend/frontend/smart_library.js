(() => {
    'use strict';

    const UI = {
        app: null,
        uploadBtn: null,
        fileInput: null,
        documentsList: null,
        statusMessage: null,
        emptyState: null,
        spinner: null
    };

    const API_ENDPOINTS = {
        DOCUMENTS: "/api/rag/documents",
        UPLOAD: "/api/rag/upload",
        DELETE: (id) => `/api/rag/document/${id}`
    };

    const ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt", ".csv", ".xlsx"];

    const getAuthHeader = () => {
        const token = localStorage.getItem("access_token");
        return token ? `Bearer ${token}` : "";
    };

    const showStatus = (message, isError = false) => {
        if (!UI.statusMessage) return;
        UI.statusMessage.textContent = message;
        UI.statusMessage.className = `sl-status show ${isError ? 'error' : 'success'}`;
        
        if (!isError) {
            setTimeout(() => {
                UI.statusMessage.className = 'sl-status';
                UI.statusMessage.textContent = '';
            }, 5000);
        }
    };

    const hideStatus = () => {
        if (!UI.statusMessage) return;
        UI.statusMessage.className = 'sl-status';
        UI.statusMessage.textContent = '';
    };

    const toggleSpinner = (show) => {
        if (!UI.spinner) return;
        if (show) {
            UI.spinner.classList.add('show');
        } else {
            UI.spinner.classList.remove('show');
        }
    };

    const toggleEmptyState = (show) => {
        if (!UI.emptyState) return;
        if (show) {
            UI.emptyState.classList.add('show');
        } else {
            UI.emptyState.classList.remove('show');
        }
    };

    const escapeHTML = (str) => {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    const renderDocuments = (documents) => {
        if (!UI.documentsList) return;
        
        UI.documentsList.innerHTML = "";

        if (!documents || documents.length === 0) {
            toggleEmptyState(true);
            return;
        }

        toggleEmptyState(false);

        const fragment = document.createDocumentFragment();

        documents.forEach(doc => {
            const card = document.createElement("div");
            card.className = "sl-card";
            
            card.innerHTML = `
                <div class="sl-card-title">
                    <span class="sl-card-icon">📄</span>
                    <span>${escapeHTML(doc.filename)}</span>
                </div>
                <div class="sl-card-actions">
                    <button type="button" class="sl-btn sl-btn-danger delete-doc-btn" data-id="${escapeHTML(String(doc.id))}">
                        <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" style="margin-right:4px;">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
                        </svg>
                        Delete
                    </button>
                </div>
            `;
            fragment.appendChild(card);
        });

        UI.documentsList.appendChild(fragment);
    };

    const loadDocuments = async () => {
        toggleSpinner(true);
        hideStatus();

        try {
            const response = await fetch(API_ENDPOINTS.DOCUMENTS, {
                method: "GET",
                headers: {
                    "Authorization": getAuthHeader(),
                    "Content-Type": "application/json"
                }
            });

            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }

            const data = await response.json();
            renderDocuments(data.documents || []);

        } catch (error) {
            console.error("[Smart Library] Load Error:", error);
            showStatus("Failed to load documents. Please try again later.", true);
            renderDocuments([]); 
        } finally {
            toggleSpinner(false);
        }
    };

    const handleUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!ALLOWED_EXTENSIONS.includes(fileExt)) {
            showStatus(`Invalid file type. Supported: ${ALLOWED_EXTENSIONS.join(", ")}`, true);
            UI.fileInput.value = ""; 
            return;
        }

        const formData = new FormData();
        formData.append("file", file);

        toggleSpinner(true);
        hideStatus();
        
        if (UI.uploadBtn) UI.uploadBtn.disabled = true;

        try {
            const response = await fetch(API_ENDPOINTS.UPLOAD, {
                method: "POST",
                headers: {
                    "Authorization": getAuthHeader()
                },
                body: formData
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.message || "Upload failed due to a server error.");
            }

            showStatus(data.message || "Document uploaded successfully!", false);
            await loadDocuments();

        } catch (error) {
            console.error("[Smart Library] Upload Error:", error);
            showStatus(error.message || "Upload failed. Please check your network and try again.", true);
        } finally {
            UI.fileInput.value = ""; 
            if (UI.uploadBtn) UI.uploadBtn.disabled = false;
            toggleSpinner(false);
        }
    };

    const handleDelete = async (documentId) => {
        if (!documentId) return;

        const isConfirmed = window.confirm("Are you sure you want to delete this document? This action cannot be undone.");
        if (!isConfirmed) return;

        toggleSpinner(true);
        hideStatus();

        try {
            const response = await fetch(API_ENDPOINTS.DELETE(documentId), {
                method: "DELETE",
                headers: {
                    "Authorization": getAuthHeader(),
                    "Content-Type": "application/json"
                }
            });

            const data = await response.json().catch(() => ({}));

            if (!response.ok) {
                throw new Error(data.message || "Deletion failed due to a server error.");
            }

            showStatus("Document deleted successfully.", false);
            await loadDocuments();

        } catch (error) {
            console.error("[Smart Library] Delete Error:", error);
            showStatus(error.message || "Failed to delete the document.", true);
        } finally {
            toggleSpinner(false);
        }
    };

    const handleAppClick = (event) => {
        const uploadBtnClick = event.target.closest("#upload-document-btn");
        if (uploadBtnClick && UI.fileInput) {
            event.preventDefault();
            UI.fileInput.click();
            return;
        }

        const deleteBtnClick = event.target.closest(".delete-doc-btn");
        if (deleteBtnClick) {
            event.preventDefault();
            const documentId = deleteBtnClick.getAttribute("data-id");
            handleDelete(documentId);
            return;
        }
    };

    const initialize = () => {
        UI.app = document.getElementById("smart-library-app");
        UI.uploadBtn = document.getElementById("upload-document-btn");
        UI.fileInput = document.getElementById("document-file");
        UI.documentsList = document.getElementById("documents-list");
        UI.statusMessage = document.getElementById("sl-status-message");
        UI.emptyState = document.getElementById("sl-empty-state");
        UI.spinner = document.getElementById("sl-spinner");

        if (!UI.app) {
            console.error("[Smart Library] App container not found.");
            return;
        }

        UI.app.addEventListener("click", handleAppClick);

        if (UI.fileInput) {
            UI.fileInput.addEventListener("change", handleUpload);
        }

        loadDocuments();
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize);
    } else {
        initialize();
    }

})();