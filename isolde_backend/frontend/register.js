// frontend/script.js (Login Logic Section)
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form') || document.querySelector('form');
    const loginBtn = document.getElementById('login-btn') || document.querySelector("button[type='submit']");
    const messageContainer = document.getElementById('message-container');

    const showMessage = (type, text) => {
        if (!messageContainer) {
            alert(text); // Fallback if message container is missing
            return;
        }
        messageContainer.textContent = text;
        messageContainer.className = `message ${type}`;
    };

    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const emailInput = document.getElementById('email');
            const passwordInput = document.getElementById('password');
            
            if (!emailInput || !passwordInput) return;

            const email = emailInput.value.trim();
            const password = passwordInput.value;

            if (!email || !password) {
                showMessage('error', 'Please fill in all fields.');
                return;
            }

            if (loginBtn) {
                loginBtn.disabled = true;
                loginBtn.style.opacity = '0.7';
                const btnText = loginBtn.querySelector('.btn-text');
                if (btnText) btnText.textContent = 'Logging in...';
            }

            try {
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });

                const data = await response.json();

                if (response.ok && data.access_token) {
                    localStorage.setItem('access_token', data.access_token);
                    showMessage('success', 'Login successful! Redirecting...');
                    setTimeout(() => {
                        window.location.href = "/";
                    }, 1000);
                } else {
                    showMessage('error', data.error || 'Invalid email or password.');
                    if (loginBtn) {
                        loginBtn.disabled = false;
                        loginBtn.style.opacity = '1';
                        const btnText = loginBtn.querySelector('.btn-text');
                        if (btnText) btnText.textContent = 'Login';
                    }
                }
            } catch (err) {
                console.error('Login failed', err);
                showMessage('error', 'Server error. Please try again later.');
                if (loginBtn) {
                    loginBtn.disabled = false;
                    loginBtn.style.opacity = '1';
                    const btnText = loginBtn.querySelector('.btn-text');
                    if (btnText) btnText.textContent = 'Login';
                }
            }
        });
    }

    // Guest Button Handler
    const guestBtn = document.getElementById('guest-btn');
    if (guestBtn) {
        guestBtn.addEventListener('click', () => {
            localStorage.removeItem('access_token');
            window.location.href = "/";
        });
    }
});