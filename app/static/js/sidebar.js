/**
 * Asana-style Sidebar Manager
 * Handles collapse/expand and view switching for the two-tier sidebar
 */

// State management
let sidebarState = {
    contentSidebarExpanded: true,
    currentView: 'default'
};

/**
 * Toggle content sidebar collapse/expand
 */
function toggleContentSidebar() {
    const contentSidebar = document.getElementById('contentSidebar');
    const collapseBtn = document.querySelector('.collapse-btn i');

    if (!contentSidebar) return;

    contentSidebar.classList.toggle('collapsed');
    sidebarState.contentSidebarExpanded = !contentSidebar.classList.contains('collapsed');

    // Update collapse button icon
    if (collapseBtn) {
        collapseBtn.className = sidebarState.contentSidebarExpanded ?
            'bi bi-chevron-left' :
            'bi bi-chevron-right';
    }

    // Save state
    saveSidebarState();
}

/**
 * Switch content view based on icon clicked
 * @param {string} view - View identifier (dashboards, crm, default, etc.)
 */
function switchContentView(view) {
    // Hide all views
    const allViews = document.querySelectorAll('.content-view');
    allViews.forEach(v => v.style.display = 'none');

    // Show selected view
    const viewElement = document.getElementById(`${view}View`);
    if (viewElement) {
        viewElement.style.display = 'block';
    } else {
        // Default to default view if specified view doesn't exist
        const defaultView = document.getElementById('defaultView');
        if (defaultView) defaultView.style.display = 'block';
    }

    // Update active icon in icon sidebar
    const iconItems = document.querySelectorAll('.icon-sidebar-item[data-view]');
    iconItems.forEach(item => {
        item.classList.remove('active');
        if (item.getAttribute('data-view') === view) {
            item.classList.add('active');
        }
    });

    // Ensure content sidebar is expanded when switching views
    const contentSidebar = document.getElementById('contentSidebar');
    if (contentSidebar && contentSidebar.classList.contains('collapsed')) {
        contentSidebar.classList.remove('collapsed');
        sidebarState.contentSidebarExpanded = true;

        const collapseBtn = document.querySelector('.collapse-btn i');
        if (collapseBtn) {
            collapseBtn.className = 'bi bi-chevron-left';
        }
    }

    // Save current view
    sidebarState.currentView = view;
    saveSidebarState();
}

/**
 * Save sidebar state to localStorage
 */
function saveSidebarState() {
    try {
        localStorage.setItem('sidebarState', JSON.stringify(sidebarState));
    } catch (e) {
        console.error('Failed to save sidebar state:', e);
    }
}

/**
 * Restore sidebar state from localStorage
 */
function restoreSidebarState() {
    try {
        const saved = localStorage.getItem('sidebarState');
        if (saved) {
            sidebarState = JSON.parse(saved);

            // Apply collapsed state
            const contentSidebar = document.getElementById('contentSidebar');
            if (contentSidebar && !sidebarState.contentSidebarExpanded) {
                contentSidebar.classList.add('collapsed');
                const collapseBtn = document.querySelector('.collapse-btn i');
                if (collapseBtn) {
                    collapseBtn.className = 'bi bi-chevron-right';
                }
            }

            // Apply current view
            if (sidebarState.currentView && sidebarState.currentView !== 'default') {
                switchContentView(sidebarState.currentView);
            }
        }
    } catch (e) {
        console.error('Failed to restore sidebar state:', e);
    }
}

/**
 * Auto-detect current view based on URL/endpoint
 */
function autoDetectView() {
    const path = window.location.pathname;

    // Check if on CRM pages
    if (path.includes('/crm/')) {
        switchContentView('crm');
        return;
    }

    // Check if on department/dashboard pages
    if (path.includes('/department/')) {
        switchContentView('dashboards');
        return;
    }

    // Default view for other pages
    switchContentView('default');
}

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialize sidebar on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();

    // Restore sidebar state
    restoreSidebarState();

    // Auto-detect view based on current page
    autoDetectView();

    // Handle icon clicks for view switching
    document.querySelectorAll('.icon-sidebar-item[data-view]').forEach(item => {
        item.addEventListener('click', function(e) {
            const view = this.getAttribute('data-view');
            if (view && !this.hasAttribute('href')) {
                e.preventDefault();
                switchContentView(view);
            }
        });
    });
});
