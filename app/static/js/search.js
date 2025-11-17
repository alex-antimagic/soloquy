/**
 * Unified Search
 * Provides autocomplete-style search across all data types
 */

let searchTimeout = null;
let currentSearchRequest = null;

/**
 * Initialize search functionality on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('globalSearch');
    const searchDropdown = document.getElementById('searchResultsDropdown');

    if (!searchInput || !searchDropdown) {
        console.error('Search elements not found');
        return;
    }

    // Handle input with debouncing
    searchInput.addEventListener('input', function(e) {
        const query = e.target.value.trim();

        // Cancel previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        // Cancel previous request
        if (currentSearchRequest) {
            currentSearchRequest.abort();
        }

        // Hide dropdown if query is too short
        if (query.length < 2) {
            hideSearchDropdown();
            return;
        }

        // Debounce search (300ms delay)
        searchTimeout = setTimeout(() => {
            performSearch(query);
        }, 300);
    });

    // Handle keyboard navigation
    searchInput.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hideSearchDropdown();
            searchInput.blur();
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            focusFirstResult();
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
            hideSearchDropdown();
        }
    });

    // Prevent dropdown from closing when clicking inside
    searchDropdown.addEventListener('click', function(e) {
        e.stopPropagation();
    });
});

/**
 * Perform search API call
 */
function performSearch(query) {
    const searchDropdown = document.getElementById('searchResultsDropdown');

    // Show loading state
    showLoadingState();

    // Create AbortController for cancellation
    const controller = new AbortController();
    currentSearchRequest = controller;

    // Make API call
    fetch(`/api/search?q=${encodeURIComponent(query)}`, {
        signal: controller.signal
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Search failed');
        }
        return response.json();
    })
    .then(data => {
        currentSearchRequest = null;
        renderSearchResults(data);
    })
    .catch(error => {
        if (error.name === 'AbortError') {
            // Request was cancelled, do nothing
            return;
        }
        console.error('Search error:', error);
        showErrorState();
    });
}

/**
 * Render search results in dropdown
 */
function renderSearchResults(data) {
    const searchDropdown = document.getElementById('searchResultsDropdown');

    if (data.total_count === 0) {
        showEmptyState();
        return;
    }

    let html = '';

    // Tasks section
    if (data.tasks && data.tasks.length > 0) {
        html += renderSection('Tasks', 'check2-square', data.tasks, renderTaskItem);
    }

    // Contacts section
    if (data.contacts && data.contacts.length > 0) {
        html += renderSection('Contacts', 'person', data.contacts, renderContactItem);
    }

    // Companies section
    if (data.companies && data.companies.length > 0) {
        html += renderSection('Companies', 'building', data.companies, renderCompanyItem);
    }

    // Deals section
    if (data.deals && data.deals.length > 0) {
        html += renderSection('Deals', 'currency-dollar', data.deals, renderDealItem);
    }

    // Tickets section
    if (data.tickets && data.tickets.length > 0) {
        html += renderSection('Support Tickets', 'headset', data.tickets, renderTicketItem);
    }

    // Messages section
    if (data.messages && data.messages.length > 0) {
        html += renderSection('Messages', 'chat-dots', data.messages, renderMessageItem);
    }

    searchDropdown.innerHTML = html;
    searchDropdown.classList.add('show');
}

/**
 * Render a category section
 */
function renderSection(title, icon, items, renderFunc) {
    let html = `
        <div class="search-section">
            <div class="search-section-header">
                <i class="bi bi-${icon} me-2"></i>${title}
            </div>
    `;

    items.forEach(item => {
        html += renderFunc(item);
    });

    html += '</div>';
    return html;
}

/**
 * Render individual result items
 */
function renderTaskItem(task) {
    const statusBadge = getStatusBadge(task.status);
    const priorityBadge = getPriorityBadge(task.priority);
    const dueDate = task.due_date ? ` • Due: ${task.due_date}` : '';

    return `
        <a href="${task.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${escapeHtml(task.title)}</div>
                <div class="result-meta">
                    ${statusBadge}
                    ${priorityBadge}
                    ${dueDate}
                </div>
            </div>
        </a>
    `;
}

function renderContactItem(contact) {
    const company = contact.company ? ` • ${escapeHtml(contact.company)}` : '';
    const jobTitle = contact.job_title ? escapeHtml(contact.job_title) : '';

    return `
        <a href="${contact.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${escapeHtml(contact.name)}</div>
                <div class="result-meta">
                    ${contact.email ? escapeHtml(contact.email) : ''}
                    ${jobTitle ? ` • ${jobTitle}` : ''}
                    ${company}
                </div>
            </div>
        </a>
    `;
}

function renderCompanyItem(company) {
    const industry = company.industry ? escapeHtml(company.industry) : '';
    const website = company.website ? ` • ${escapeHtml(company.website)}` : '';

    return `
        <a href="${company.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${escapeHtml(company.name)}</div>
                <div class="result-meta">
                    ${industry}
                    ${website}
                </div>
            </div>
        </a>
    `;
}

function renderDealItem(deal) {
    const statusBadge = getStatusBadge(deal.status);
    const amount = deal.amount ? ` • $${deal.amount.toLocaleString()}` : '';
    const company = deal.company ? ` • ${escapeHtml(deal.company)}` : '';

    return `
        <a href="${deal.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${escapeHtml(deal.name)}</div>
                <div class="result-meta">
                    ${statusBadge}
                    ${amount}
                    ${company}
                </div>
            </div>
        </a>
    `;
}

function renderTicketItem(ticket) {
    const statusBadge = getStatusBadge(ticket.status);
    const priorityBadge = getPriorityBadge(ticket.priority);

    return `
        <a href="${ticket.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${ticket.ticket_number}: ${escapeHtml(ticket.subject)}</div>
                <div class="result-meta">
                    ${statusBadge}
                    ${priorityBadge}
                </div>
            </div>
        </a>
    `;
}

function renderMessageItem(message) {
    return `
        <a href="${message.url}" class="search-result-item">
            <div class="result-content">
                <div class="result-title">${escapeHtml(message.preview)}</div>
                <div class="result-meta">
                    ${escapeHtml(message.sender)} in ${escapeHtml(message.context)} • ${message.created_at}
                </div>
            </div>
        </a>
    `;
}

/**
 * Helper functions for badges
 */
function getStatusBadge(status) {
    const statusMap = {
        'pending': 'warning',
        'in_progress': 'primary',
        'completed': 'success',
        'open': 'info',
        'won': 'success',
        'lost': 'danger',
        'new': 'info',
        'resolved': 'success',
        'closed': 'secondary'
    };
    const color = statusMap[status] || 'secondary';
    return `<span class="badge bg-${color}">${status.replace('_', ' ')}</span>`;
}

function getPriorityBadge(priority) {
    if (!priority) return '';

    const priorityMap = {
        'low': 'secondary',
        'medium': 'info',
        'high': 'warning',
        'urgent': 'danger'
    };
    const color = priorityMap[priority] || 'secondary';
    return `<span class="badge bg-${color}">${priority}</span>`;
}

/**
 * State management functions
 */
function showLoadingState() {
    const searchDropdown = document.getElementById('searchResultsDropdown');
    searchDropdown.innerHTML = `
        <div class="search-loading">
            <div class="spinner-border spinner-border-sm text-primary me-2" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            Searching...
        </div>
    `;
    searchDropdown.classList.add('show');
}

function showEmptyState() {
    const searchDropdown = document.getElementById('searchResultsDropdown');
    searchDropdown.innerHTML = `
        <div class="search-empty">
            <i class="bi bi-search fs-4 mb-2 d-block text-muted"></i>
            <div class="text-muted">No results found</div>
        </div>
    `;
    searchDropdown.classList.add('show');
}

function showErrorState() {
    const searchDropdown = document.getElementById('searchResultsDropdown');
    searchDropdown.innerHTML = `
        <div class="search-empty">
            <i class="bi bi-exclamation-circle fs-4 mb-2 d-block text-danger"></i>
            <div class="text-danger">Search failed. Please try again.</div>
        </div>
    `;
    searchDropdown.classList.add('show');
}

function hideSearchDropdown() {
    const searchDropdown = document.getElementById('searchResultsDropdown');
    searchDropdown.classList.remove('show');
    searchDropdown.innerHTML = '';
}

/**
 * Keyboard navigation
 */
function focusFirstResult() {
    const firstLink = document.querySelector('.search-result-item');
    if (firstLink) {
        firstLink.focus();
    }
}

/**
 * Utility functions
 */
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
        .toString()
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
