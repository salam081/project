/**
 * Advanced Sidebar Management System
 * Handles desktop collapse/expand and mobile slide-in functionality
 */
class SidebarManager {
    constructor() {
        // DOM Elements
        this.sidebar = document.getElementById('sidebar');
        this.mainContent = document.getElementById('mainContent');
        this.sidebarOverlay = document.getElementById('sidebarOverlay');
        this.desktopToggle = document.getElementById('desktopToggle');
        this.mobileToggle = document.getElementById('mobileToggle');
        this.toggleIcon = document.getElementById('toggleIcon');
        
        // State management
        this.isCollapsed = false;
        this.isMobile = window.innerWidth < 992;
        this.isInitialized = false;
        
        // Initialize the sidebar system
        this.init();
    }
    
    /**
     * Initialize the sidebar system
     */
    init() {
        if (this.isInitialized) return;
        
        this.setupEventListeners();
        this.handleResize();
        this.setupNavigation();
        this.loadSavedState();
        
        this.isInitialized = true;
        
        // Debug log
        console.log('SidebarManager initialized', {
            isMobile: this.isMobile,
            elements: {
                sidebar: !!this.sidebar,
                desktopToggle: !!this.desktopToggle,
                mobileToggle: !!this.mobileToggle
            }
        });
    }
    
    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        // Desktop toggle button
        if (this.desktopToggle) {
            this.desktopToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleDesktopSidebar();
            });
        }
        
        // Mobile toggle button
        if (this.mobileToggle) {
            this.mobileToggle.addEventListener('click', (e) => {
                e.preventDefault();
                this.toggleMobileSidebar();
            });
        }
        
        // Overlay click to close mobile sidebar
        if (this.sidebarOverlay) {
            this.sidebarOverlay.addEventListener('click', () => {
                this.closeMobileSidebar();
            });
        }
        
        // Window resize handler
        window.addEventListener('resize', this.debounce(() => {
            this.handleResize();
        }, 250));
        
        // Escape key handler for mobile
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isMobile && this.sidebar?.classList.contains('mobile-show')) {
                this.closeMobileSidebar();
            }
        });
        
        // Prevent body scroll when mobile sidebar is open
        document.addEventListener('touchmove', (e) => {
            if (this.isMobile && this.sidebar?.classList.contains('mobile-show')) {
                if (!this.sidebar.contains(e.target)) {
                    e.preventDefault();
                }
            }
        }, { passive: false });
    }
    
    /**
     * Toggle desktop sidebar (collapse/expand)
     */
    toggleDesktopSidebar() {
        if (this.isMobile) return;
        
        if (this.isCollapsed) {
            this.expandSidebar();
        } else {
            this.collapseSidebar();
        }
    }
    
    /**
     * Collapse the sidebar (desktop only)
     */
    collapseSidebar() {
        if (!this.sidebar || this.isMobile) return;
        
        this.sidebar.classList.add('collapsed');
        this.mainContent?.classList.add('expanded');
        
        if (this.toggleIcon) {
            this.toggleIcon.className = 'bi bi-chevron-right';
        }
        
        this.isCollapsed = true;
        this.saveState();
        
        // Announce to screen readers
        this.announceToScreenReader('Sidebar collapsed');
    }
    
    /**
     * Expand the sidebar (desktop only)
     */
    expandSidebar() {
        if (!this.sidebar || this.isMobile) return;
        
        this.sidebar.classList.remove('collapsed');
        this.mainContent?.classList.remove('expanded');
        
        if (this.toggleIcon) {
            this.toggleIcon.className = 'bi bi-chevron-left';
        }
        
        this.isCollapsed = false;
        this.saveState();
        
        // Announce to screen readers
        this.announceToScreenReader('Sidebar expanded');
    }
    
    /**
     * Toggle mobile sidebar (show/hide)
     */
    toggleMobileSidebar() {
        if (!this.isMobile) return;
        
        if (this.sidebar?.classList.contains('mobile-show')) {
            this.closeMobileSidebar();
        } else {
            this.openMobileSidebar();
        }
    }
    
    /**
     * Open mobile sidebar
     */
    openMobileSidebar() {
        if (!this.sidebar || !this.isMobile) return;
        
        this.sidebar.classList.add('mobile-show');
        this.sidebarOverlay?.classList.add('show');
        
        // Prevent body scroll
        document.body.style.overflow = 'hidden';
        
        // Focus management
        const firstFocusable = this.sidebar.querySelector('a, button');
        if (firstFocusable) {
            setTimeout(() => firstFocusable.focus(), 100);
        }
        
        // Announce to screen readers
        this.announceToScreenReader('Navigation menu opened');
    }
    
    /**
     * Close mobile sidebar
     */
    closeMobileSidebar() {
        if (!this.sidebar) return;
        
        this.sidebar.classList.remove('mobile-show');
        this.sidebarOverlay?.classList.remove('show');
        
        // Restore body scroll
        document.body.style.overflow = '';
        
        // Return focus to mobile toggle button
        if (this.mobileToggle) {
            this.mobileToggle.focus();
        }
        
        // Announce to screen readers
        this.announceToScreenReader('Navigation menu closed');
    }
    
    /**
     * Handle window resize events
     */
    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth < 992;
        
        // If we switched between mobile and desktop
        if (wasMobile !== this.isMobile) {
            if (this.isMobile) {
                // Switched to mobile
                this.resetToMobile();
            } else {
                // Switched to desktop
                this.resetToDesktop();
            }
        }
    }
    
    /**
     * Reset sidebar for mobile view
     */
    resetToMobile() {
        if (!this.sidebar) return;
        
        // Remove desktop classes
        this.sidebar.classList.remove('collapsed');
        this.mainContent?.classList.remove('expanded');
        
        // Close mobile sidebar if open
        this.closeMobileSidebar();
        
        // Reset toggle icon
        if (this.toggleIcon) {
            this.toggleIcon.className = 'bi bi-chevron-left';
        }
    }
    
    /**
     * Reset sidebar for desktop view
     */
    resetToDesktop() {
        if (!this.sidebar) return;
        
        // Remove mobile classes
        this.sidebar.classList.remove('mobile-show');
        this.sidebarOverlay?.classList.remove('show');
        document.body.style.overflow = '';
        
        // Restore collapsed state if it was saved
        this.loadSavedState();
    }
    
    /**
     * Save sidebar state to localStorage
     */
    saveState() {
        try {
            localStorage.setItem('sidebarCollapsed', this.isCollapsed.toString());
        } catch (e) {
            console.warn('Could not save sidebar state:', e);
        }
    }
    
    /**
     * Load saved sidebar state from localStorage
     */
    loadSavedState() {
        if (this.isMobile) return;
        
        try {
            const savedState = localStorage.getItem('sidebarCollapsed');
            if (savedState === 'true') {
                this.collapseSidebar();
            } else {
                this.expandSidebar();
            }
        } catch (e) {
            console.warn('Could not load sidebar state:', e);
            // Default to expanded if we can't load state
            this.expandSidebar();
        }
    }
    
    /**
     * Set up navigation functionality
     */
    setupNavigation() {
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        const sections = document.querySelectorAll('.content-section');
        
        // Handle navigation link clicks
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                
                const targetSection = link.getAttribute('data-section');
                this.navigateToSection(targetSection, link);
                
                // Close mobile sidebar after navigation
                if (this.isMobile) {
                    this.closeMobileSidebar();
                }
            });
        });
        
        // Handle browser back/forward buttons
        window.addEventListener('popstate', (e) => {
            const hash = window.location.hash.substring(1);
            if (hash) {
                this.navigateToSection(hash);
            }
        });
        
        // Handle initial page load with hash
        const initialHash = window.location.hash.substring(1);
        if (initialHash) {
            this.navigateToSection(initialHash);
        }
    }
    
    /**
     * Navigate to a specific section
     */
    navigateToSection(sectionId, clickedLink = null) {
        const sections = document.querySelectorAll('.content-section');
        const navLinks = document.querySelectorAll('.nav-link[data-section]');
        
        // Update active nav link
        navLinks.forEach(link => {
            link.classList.remove('active');
            if (link.getAttribute('data-section') === sectionId || link === clickedLink) {
                link.classList.add('active');
            }
        });
        
        // Show target section, hide others
        sections.forEach(section => {
            if (section.id === sectionId) {
                section.classList.add('active');
                section.style.display = 'block';
            } else {
                section.classList.remove('active');
                section.style.display = 'none';
            }
        });
        
        // Update URL hash without triggering page jump
        if (window.location.hash !== `#${sectionId}`) {
            history.pushState(null, null, `#${sectionId}`);
        }
        
        // Scroll to top of main content
        if (this.mainContent) {
            this.mainContent.scrollTop = 0;
        }
    }
    
    /**
     * Announce changes to screen readers
     */
    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('aria-live', 'polite');
        announcement.setAttribute('aria-atomic', 'true');
        announcement.classList.add('sr-only');
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        // Remove after announcement
        setTimeout(() => {
            document.body.removeChild(announcement);
        }, 1000);
    }
    
    /**
     * Debounce function to limit rapid calls
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Get current sidebar state
     */
    getState() {
        return {
            isCollapsed: this.isCollapsed,
            isMobile: this.isMobile,
            mobileOpen: this.sidebar?.classList.contains('mobile-show') || false
        };
    }
    
    /**
     * Destroy the sidebar manager (cleanup)
     */
    destroy() {
        // Remove event listeners
        window.removeEventListener('resize', this.handleResize);
        document.removeEventListener('keydown', this.handleKeydown);
        
        // Reset body styles
        document.body.style.overflow = '';
        
        // Mark as not initialized
        this.isInitialized = false;
    }
}

/**
 * Additional utility functions
 */

/**
 * Initialize tooltips for buttons (if needed)
 */
function initializeTooltips() {
    const tooltipElements = document.querySelectorAll('[title]');
    tooltipElements.forEach(element => {
        // You can add tooltip library initialization here if needed
        // For now, we're using native title attributes
    });
}

/**
 * Handle smooth scrolling for anchor links
 */
function initializeSmoothScrolling() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

/**
 * Initialize dropdown accessibility
 */
function initializeDropdownAccessibility() {
    const dropdownButtons = document.querySelectorAll('[data-bs-toggle="collapse"]');
    
    dropdownButtons.forEach(button => {
        button.addEventListener('click', function() {
            const isExpanded = this.getAttribute('aria-expanded') === 'true';
            this.setAttribute('aria-expanded', !isExpanded);
        });
    });
}

/**
 * Initialize the entire dashboard system
 */
function initializeDashboard() {
    // Initialize sidebar manager
    const sidebarManager = new SidebarManager();
    
    // Initialize other components
    initializeTooltips();
    initializeSmoothScrolling();
    initializeDropdownAccessibility();
    
    // Make sidebar manager globally available for debugging
    window.sidebarManager = sidebarManager;
    
    // Log initialization
    console.log('Dashboard initialized successfully');
    
    return sidebarManager;
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    // DOM is already ready
    initializeDashboard();
}

// Handle page visibility changes
document.addEventListener('visibilitychange', function() {
    if (document.visibilityState === 'visible') {
        // Page became visible, refresh layout if needed
        if (window.sidebarManager) {
            window.sidebarManager.handleResize();
        }
    }
});

// Export for module systems (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { SidebarManager, initializeDashboard };
}