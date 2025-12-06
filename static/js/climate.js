let tempChart = null;

document.addEventListener('DOMContentLoaded', function () {
    const form = document.getElementById('trend-form');
    const btn = document.getElementById('load-trends-btn');
    const cityInput = document.getElementById('city-select');
    const yearsSelect = document.getElementById('years');
    const canvas = document.getElementById('tempChart');

    if (!form || !btn || !cityInput || !yearsSelect || !canvas) {
        console.error("Climate trends form elements not found on this page.");
        return;
    }

    const ctx = canvas.getContext('2d');

    btn.addEventListener('click', function () {
        const city = cityInput.value.trim();
        const years = yearsSelect.value;

        if (!city) {
            alert("Please enter a city.");
            return;
        }

        // Simple loading state
        btn.disabled = true;
        const oldText = btn.textContent;
        btn.textContent = "Loading...";

        fetch('/api/trends', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                city: city,
                years: years
            })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error("Network response was not ok");
                }
                return response.json();
            })
            .then(data => {
                console.log("Trends data:", data);
                btn.disabled = false;
                btn.textContent = oldText;

                if (data.error) {
                    alert(data.error);
                    return;
                }

                const labels = data.months || [];
                const temps = data.avg_temps || [];

                // Destroy previous chart if exists
                if (tempChart) {
                    tempChart.destroy();
                }

                tempChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: `Avg Temperature (${data.city})`,
                            data: temps,
                            borderWidth: 2,
                            fill: false,
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: false
                            }
                        }
                    }
                });
            })
            .catch(err => {
                console.error("Error loading trends:", err);
                btn.disabled = false;
                btn.textContent = oldText;
                alert("Error loading climate trends. Check console for details.");
            });
    });
});
