// Core JavaScript - Smart Online Exam Management System

document.addEventListener('DOMContentLoaded', () => {
    // Theme Toggling Logic
    const themeToggleBtn = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;

    // Load user's saved theme from localStorage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        htmlElement.classList.add('light-mode');
        updateThemeToggleIcon('light');
    } else {
        htmlElement.classList.remove('light-mode');
        updateThemeToggleIcon('dark');
    }

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            htmlElement.classList.toggle('light-mode');
            const isLight = htmlElement.classList.contains('light-mode');
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
            updateThemeToggleIcon(isLight ? 'light' : 'dark');
        });
    }

    function updateThemeToggleIcon(theme) {
        if (!themeToggleBtn) return;
        if (theme === 'light') {
            themeToggleBtn.innerHTML = '🌙'; // Icon to switch back to dark mode
            themeToggleBtn.title = 'Switch to Dark Mode';
        } else {
            themeToggleBtn.innerHTML = '☀️'; // Icon to switch to light mode
            themeToggleBtn.title = 'Switch to Light Mode';
        }
    }

    // Flash Alert Dismissal
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        const closeBtn = alert.querySelector('.alert-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                alert.style.opacity = '0';
                setTimeout(() => alert.remove(), 300);
            });
        }
    });
});
