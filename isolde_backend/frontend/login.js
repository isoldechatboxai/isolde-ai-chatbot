const loginForm = document.getElementById("loginForm");

loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                email: email,
                password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Login failed");
            return;
        }

        // Save JWT Token
        localStorage.setItem("access_token", data.access_token);

        // Save User Details (optional)
        localStorage.setItem("user", JSON.stringify(data.user));

        alert("Login Successful!");

        // Redirect to chatbot
        window.location.href = "index.html";

    } catch (error) {
        console.error(error);
        alert("Unable to connect to server.");
    }
});