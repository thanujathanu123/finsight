// Theme-aware chart options
function getChartOptions(isDark) {
    return {
        responsive: true,
        scales: {
            y: {
                beginAtZero: true,
                ticks: {
                    stepSize: 1,
                    color: isDark ? 'rgba(255, 255, 255, 0.7)' : undefined
                },
                grid: {
                    color: isDark ? 'rgba(255, 255, 255, 0.1)' : undefined
                }
            },
            x: {
                ticks: {
                    color: isDark ? 'rgba(255, 255, 255, 0.7)' : undefined
                },
                grid: {
                    color: isDark ? 'rgba(255, 255, 255, 0.1)' : undefined
                }
            }
        },
        plugins: {
            title: {
                display: true,
                text: 'Risk Score Distribution',
                color: isDark ? '#ffffff' : undefined
            },
            legend: {
                labels: {
                    color: isDark ? 'rgba(255, 255, 255, 0.7)' : undefined
                }
            }
        }
    };
}

// Store chart instances
let charts = {};

// Update charts theme
function updateChartsTheme(isDark) {
    Object.values(charts).forEach(chart => {
        chart.options = { ...chart.options, ...getChartOptions(isDark) };
        chart.update('none');
    });
}

// Theme change observer
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (mutation.attributeName === 'data-bs-theme') {
            const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
            updateChartsTheme(isDark);
        }
    });

    // Start observing theme changes
    observer.observe(document.documentElement, {
        attributes: true,
        attributeFilter: ['data-bs-theme']
    });
});

// Dashboard initialization
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    });

    // Initialize DataTables
    $('.datatable').DataTable({
        pageLength: 25,
        responsive: true,
        dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
             '<"row"<"col-sm-12"tr>>' +
             '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
        language: {
            search: "Search transactions:",
            lengthMenu: "Show _MENU_ entries per page",
        }
    });

    // Risk Score Chart (if element exists)
    const riskChartEl = document.getElementById('riskDistributionChart');
    if (riskChartEl) {
        const isDark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
        charts.riskDistribution = new Chart(riskChartEl, {
            type: 'bar',
            data: {
                labels: ['Low Risk (0-30)', 'Medium Risk (31-70)', 'High Risk (71-100)'],
                datasets: [{
                    label: 'Number of Transactions',
                    data: [0, 0, 0], // Will be populated by view
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.5)',
                        'rgba(255, 193, 7, 0.5)',
                        'rgba(220, 53, 69, 0.5)'
                    ],
                    borderColor: [
                        'rgb(40, 167, 69)',
                        'rgb(255, 193, 7)',
                        'rgb(220, 53, 69)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    title: {
                        display: true,
                        text: 'Risk Score Distribution'
                    }
                }
            }
        });
    }
});
