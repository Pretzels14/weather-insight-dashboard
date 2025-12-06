document.getElementById('load-trends').addEventListener('click', async () => {
    const city = document.getElementById('city-input').value || 'Chicago';
    const years = document.getElementById('years-select').value || '30';
    const status = document.getElementById('status');
    status.innerText = 'Loading...';

    const res = await fetch('/api/trends', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({city, years})
    });
    const data = await res.json();
    if (data.error) {
        status.innerText = 'Error: ' + data.error;
        return;
    }
    status.innerText = 'Rendering charts for ' + data.city;

    // Temperature chart
    const tempCtx = document.getElementById('tempChart').getContext('2d');
    if (window.tempChart) window.tempChart.destroy();
    window.tempChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: data.months,
            datasets: [{
                label: `Avg Monthly Temp (${data.city})`,
                data: data.avg_temps,
                fill: false,
                tension: 0.2
            }]
        },
        options: {
            responsive: true,
            scales: { y: { beginAtZero: false } }
        }
    });

    // Precip chart
    const precipCtx = document.getElementById('precipChart').getContext('2d');
    if (window.precipChart) window.precipChart.destroy();
    window.precipChart = new Chart(precipCtx, {
        type: 'bar',
        data: {
            labels: data.months,
            datasets: [{
                label: `Avg Monthly Precipitation (${data.city})`,
                data: data.avg_precips,
                barPercentage: 0.6
            }]
        },
        options: {
            responsive: true,
            scales: { y: { beginAtZero: true } }
        }
    });
});
