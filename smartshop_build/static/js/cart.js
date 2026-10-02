document.addEventListener("DOMContentLoaded", function () {
    const forms = document.querySelectorAll(
        ".add-to-cart-form"
    );

    forms.forEach(function (form) {
        form.addEventListener(
            "submit",
            async function (event) {
                event.preventDefault();

                const button = form.querySelector(
                    ".add-cart-button"
                );

                if (!button) {
                    return;
                }

                const oldText = button.textContent;

                button.disabled = true;
                button.textContent = "Adding...";

                try {
                    const response = await fetch(
                        form.action,
                        {
                            method: "POST",
                            body: new FormData(form),
                            headers: {
                                "X-Requested-With":
                                    "XMLHttpRequest",
                                "Accept":
                                    "application/json"
                            }
                        }
                    );

                    const responseText =
                        await response.text();

                    let data;

                    try {
                        data = JSON.parse(
                            responseText
                        );
                    } catch (error) {
                        console.error(
                            "Server response:",
                            responseText
                        );

                        throw new Error(
                            "Server error. Check the terminal."
                        );
                    }

                    if (
                        !response.ok ||
                        !data.success
                    ) {
                        throw new Error(
                            data.message ||
                            "Unable to add product."
                        );
                    }

                    const cartCount =
                        document.getElementById(
                            "cart-count"
                        );

                    if (cartCount) {
                        cartCount.textContent =
                            data.cart_count;
                    }

                    button.textContent = "Added";

                    showToast(
                        data.message,
                        "success"
                    );

                    setTimeout(function () {
                        button.textContent = oldText;
                        button.disabled = false;
                    }, 1200);

                } catch (error) {
                    console.error(
                        "Cart error:",
                        error
                    );

                    showToast(
                        error.message,
                        "danger"
                    );

                    button.textContent = oldText;
                    button.disabled = false;
                }
            }
        );
    });

    function showToast(message, type) {
        const oldToast =
            document.querySelector(".ajax-toast");

        if (oldToast) {
            oldToast.remove();
        }

        const toast =
            document.createElement("div");

        toast.className =
            "ajax-toast " + type;

        toast.textContent = message;

        document.body.appendChild(toast);

        setTimeout(function () {
            toast.classList.add("show");
        }, 10);

        setTimeout(function () {
            toast.classList.remove("show");

            setTimeout(function () {
                toast.remove();
            }, 300);
        }, 3000);
    }
});