// Common functionality for the application
document.addEventListener('DOMContentLoaded', function() {
    // Enable all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Password visibility toggle with enhanced animation
    const passwordToggles = document.querySelectorAll('.toggle-password');
    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const targetField = this.closest('.input-group').querySelector('input');
            const icon = this.querySelector('i');
            
            if (targetField.type === 'password') {
                targetField.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
                
                // Add subtle highlight animation
                targetField.classList.add('highlight-field');
                setTimeout(() => {
                    targetField.classList.remove('highlight-field');
                }, 500);
            } else {
                targetField.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        });
    });
    
    // Enhanced form validation
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        // Add input event listeners for real-time validation
        form.querySelectorAll('input, select, textarea').forEach(input => {
            input.addEventListener('input', function() {
                if (this.checkValidity()) {
                    this.classList.remove('is-invalid');
                    this.classList.add('is-valid');
                } else {
                    this.classList.remove('is-valid');
                    this.classList.add('is-invalid');
                }
            });
        });
        
        // Form submission validation
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Add shake animation to invalid fields
                form.querySelectorAll(':invalid').forEach(field => {
                    field.classList.add('shake-field');
                    setTimeout(() => {
                        field.classList.remove('shake-field');
                    }, 600);
                });
                
                // Scroll to first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus();
                }
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Auto-resize textareas
    const textareas = document.querySelectorAll('textarea.auto-resize');
    textareas.forEach(textarea => {
        function autoResize() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        }
        
        textarea.addEventListener('input', autoResize);
        
        // Initial resize
        if (textarea.value) {
            autoResize.call(textarea);
        }
    });
    
    // Add delay loading effect for better UX
    window.addEventListener('load', function() {
        document.body.classList.add('loaded');
        
        // Animate elements into view when they become visible
        animateElementsOnScroll();
    });
    
    // Highlight current page in navigation
    highlightCurrentNavItem();
    
    // Initialize animated counters
    initCounters();
    
    // Add ripple effect to buttons
    initRippleEffect();
});

// Function to animate elements as they scroll into view
function animateElementsOnScroll() {
    const animatedElements = document.querySelectorAll('.animate-on-scroll:not(.animated)');
    
    if ('IntersectionObserver' in window) {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('animated');
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.1 });
        
        animatedElements.forEach(element => {
            observer.observe(element);
        });
    } else {
        // Fallback for browsers without IntersectionObserver
        animatedElements.forEach(element => {
            element.classList.add('animated');
        });
    }
}

// Highlight current nav item based on URL
function highlightCurrentNavItem() {
    const currentUrl = window.location.pathname;
    document.querySelectorAll('.navbar-nav .nav-link').forEach(link => {
        if (link.getAttribute('href') === currentUrl) {
            link.classList.add('active');
        }
    });
}

// Animated counter initialization
function initCounters() {
    const counters = document.querySelectorAll('.counter');
    
    if (!counters.length) return;
    
    counters.forEach(counter => {
        const target = parseInt(counter.getAttribute('data-target'));
        const duration = parseInt(counter.getAttribute('data-duration') || '1000');
        const increment = target / (duration / 16);
        let current = 0;
        
        const updateCounter = () => {
            current += increment;
            if (current < target) {
                counter.textContent = Math.ceil(current);
                requestAnimationFrame(updateCounter);
            } else {
                counter.textContent = target;
            }
        };
        
        if ('IntersectionObserver' in window) {
            const observer = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        updateCounter();
                        observer.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.5 });
            
            observer.observe(counter);
        } else {
            // Fallback
            updateCounter();
        }
    });
}

// Add ripple effect to buttons
function initRippleEffect() {
    const buttons = document.querySelectorAll('.btn:not(.no-ripple)');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const x = e.clientX - this.getBoundingClientRect().left;
            const y = e.clientY - this.getBoundingClientRect().top;
            
            const ripple = document.createElement('span');
            ripple.classList.add('ripple-effect');
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
}

// Format input fields with specific requirements
function formatPhoneNumber(input) {
    let value = input.value.replace(/\D/g, '');
    let formattedValue = '';
    
    if (value.length > 0) {
        formattedValue = value.substring(0, 3);
        if (value.length >= 4) {
            formattedValue += '-' + value.substring(3, 6);
        }
        if (value.length >= 7) {
            formattedValue += '-' + value.substring(6, 10);
        }
    }
    
    input.value = formattedValue;
}
