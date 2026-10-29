/* Progressive enhancement: forms and links also work without JavaScript. */
(() => {
    "use strict";

    const ajaxHeaders = { "X-Requested-With": "XMLHttpRequest", "Accept": "application/json" };
    let filterController;
    let filterVersion = 0;

    function status(scope, text, error = false) {
        const element = scope.querySelector("[data-review-status], [data-form-status], [data-action-error]")
            || scope.closest("[data-review-page]")?.querySelector("[data-review-status]");
        if (!element) return;
        element.textContent = text;
        element.hidden = false;
        element.classList.toggle("is-error", error);
    }

    async function loadReviews(url, push = false) {
        const page = document.querySelector("[data-review-page]");
        if (!page) return;
        const panel = page.querySelector("[data-review-panel]");
        if (filterController) filterController.abort();
        filterController = new AbortController();
        const version = ++filterVersion;
        panel.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(url, {
                headers: ajaxHeaders, credentials: "same-origin", signal: filterController.signal,
            });
            if (response.redirected) { window.location.assign(response.url); return; }
            if (!response.ok) throw new Error("Could not load reviews. Please try again.");
            const data = await response.json();
            if (version !== filterVersion) return;
            panel.innerHTML = data.html;
            if (push) history.pushState({}, "", url);
            status(page, "Reviews updated.");
        } catch (error) {
            if (error.name !== "AbortError") status(page, error.message, true);
        } finally {
            if (version === filterVersion) panel.removeAttribute("aria-busy");
        }
    }

    document.addEventListener("click", (event) => {
        const link = event.target.closest("a[data-review-filter]");
        if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        loadReviews(link.href, true);
    });

    window.addEventListener("popstate", () => {
        if (document.querySelector("[data-review-page]")) loadReviews(window.location.href);
    });

    document.addEventListener("submit", async (event) => {
        const form = event.target;
        if (!form.matches("[data-review-form], [data-review-action]")) return;
        event.preventDefault();
        if (form.dataset.submitting === "true") return;
        form.dataset.submitting = "true";
        const buttons = [...form.querySelectorAll('button[type="submit"]')];
        const body = new FormData(form);
        const token = form.querySelector('[name="csrfmiddlewaretoken"]').value;
        buttons.forEach((button) => { button.disabled = true; });
        form.setAttribute("aria-busy", "true");
        try {
            const response = await fetch(form.action || window.location.href, {
                method: "POST", body, credentials: "same-origin",
                headers: { ...ajaxHeaders, "X-CSRFToken": token },
            });
            if (response.redirected) { window.location.assign(response.url); return; }
            if (!response.headers.get("content-type")?.includes("application/json")) {
                throw new Error(response.status === 403
                    ? "This action is not allowed or your session expired. Refresh and try again."
                    : "Something went wrong. Please try again.");
            }
            const data = await response.json();
            if (!response.ok) {
                if (data.html) {
                    form.querySelector("[data-form-fields]").innerHTML = data.html;
                    status(form, "Please check the highlighted fields.", true);
                    const error = form.querySelector(".errorlist");
                    if (error) error.scrollIntoView({ block: "center", behavior: "smooth" });
                } else {
                    const errors = Object.values(data.errors || {}).flat().join(" ");
                    status(form, errors || "Please check your input.", true);
                }
                return;
            }
            if (form.matches("[data-review-action]")) {
                await loadReviews(window.location.href);
                status(document.querySelector("[data-review-page]"), data.message);
            } else {
                sessionStorage.setItem("gaia-review-message", data.message);
                window.location.assign(data.redirect_url);
            }
        } catch (error) {
            status(form, error.message || "Unable to connect. Your changes have not been confirmed.", true);
        } finally {
            form.dataset.submitting = "false";
            form.removeAttribute("aria-busy");
            buttons.forEach((button) => { button.disabled = false; });
        }
    });

    const message = sessionStorage.getItem("gaia-review-message");
    const reviewPage = document.querySelector("[data-review-page]");
    if (message && reviewPage) {
        status(reviewPage, message);
        sessionStorage.removeItem("gaia-review-message");
    }
})();
