document.addEventListener("DOMContentLoaded", () => {

    /* ================= CHART ================= */
    const chartCanvas = document.getElementById("violationChart");

    if (chartCanvas) {
        const labels = JSON.parse(chartCanvas.dataset.labels);
        const values = JSON.parse(chartCanvas.dataset.values);

        new Chart(chartCanvas.getContext("2d"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    borderColor: "#4f46e5",
                    backgroundColor: "rgba(79,70,229,0.12)",
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    /* ================= CAMERA ACCESS ================= */
    const cameraBtn = document.getElementById("cameraBtn");

    if (cameraBtn) {
        cameraBtn.addEventListener("click", () => {
            window.location.href = "/admin/camera";
        });
    }

});

document.querySelectorAll(".submenu-toggle").forEach(toggle => {
    toggle.addEventListener("click", e => {
        e.preventDefault();
        toggle.parentElement.classList.toggle("expanded");
    });
});
