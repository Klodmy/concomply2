document.addEventListener("DOMContentLoaded", () => {
    const revealItems = document.querySelectorAll("[data-reveal]");
    revealItems.forEach((item, index) => {
        item.classList.add("reveal");
        item.style.animationDelay = `${index * 80}ms`;
    });

    const costSections = document.querySelectorAll("[data-cost-items]");
    costSections.forEach((section) => {
        const addButton = section.querySelector("[data-add-item]");
        const templateRow = section.querySelector("[data-cost-row]");

        const updateRemoveButtons = () => {
            const rows = section.querySelectorAll("[data-cost-row]");
            rows.forEach((row, index) => {
                const removeButton = row.querySelector("[data-remove-item]");
                if (removeButton) {
                    removeButton.disabled = rows.length === 1;
                    removeButton.style.opacity = rows.length === 1 ? "0.5" : "1";
                }
                if (index > 0) {
                    row.classList.add("is-clone");
                }
            });
        };

        const addRow = () => {
            const clone = templateRow.cloneNode(true);
            clone.querySelectorAll("input").forEach((input) => {
                input.value = "";
            });
            section.appendChild(clone);
            updateRemoveButtons();
        };

        section.addEventListener("click", (event) => {
            const removeButton = event.target.closest("[data-remove-item]");
            if (removeButton) {
                const rows = section.querySelectorAll("[data-cost-row]");
                if (rows.length > 1) {
                    removeButton.closest("[data-cost-row]").remove();
                    updateRemoveButtons();
                }
            }
        });

        if (addButton) {
            addButton.addEventListener("click", addRow);
        }

        updateRemoveButtons();
    });
});
