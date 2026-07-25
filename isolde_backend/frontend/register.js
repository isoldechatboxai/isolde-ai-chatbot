const registerForm = document.getElementById("registerForm");

registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = document.getElementById("username").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
        const response = await fetch("/api/register", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
    name: username,
    email: email,
    password: password
            })
        });

        const data = await response.json();

        if (!response.ok) {
            alert(data.error || "Registration failed");
            return;
        }

        alert("Registration Successful!");

        window.location.href = "login.html";

    } catch (error) {
        console.error(error);
        alert("Unable to connect to server.");
    }
});