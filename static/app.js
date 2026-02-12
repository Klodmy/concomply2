document.addEventListener("DOMContentLoaded", () => {
    const revealItems = document.querySelectorAll("[data-reveal]");
    revealItems.forEach((item, index) => {
        item.classList.add("reveal");
        item.style.animationDelay = `${index * 80}ms`;
    });
});
