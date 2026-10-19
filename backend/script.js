const API_BASE_URL = 'http://127.0.0.1:8000/api';
let metricsChartInstance = null;

// Initialize app data on load
document.addEventListener('DOMContentLoaded', () => {
  loadMetrics();
  fetchExperimentMetrics();
});

// Load Single Metric Summary
async function loadMetrics() {
  try {
    const response = await fetch(`${API_BASE_URL}/metrics/`);
    if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
    const data = await response.json();
    
    const accuracy = data.accuracy !== undefined ? (data.accuracy * 100).toFixed(1) : '--';
    document.getElementById('accuracy-value').innerText = `${accuracy}%`;
  } catch (error) {
    console.error('Failed to load summary metrics:', error);
    document.getElementById('accuracy-value').innerText = 'N/A';
  }
}

// Handle Sentiment Form Submission
document.getElementById('review-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const reviewInput = document.getElementById('review-input').value.trim();
  const modelSelect = document.getElementById('model-select').value;
  const submitBtn = document.getElementById('submit-btn');
  const resultContainer = document.getElementById('result-container');
  const resultSentiment = document.getElementById('result-sentiment');
  const resultConfidence = document.getElementById('result-confidence');

  if (!reviewInput) return;

  submitBtn.disabled = true;
  submitBtn.textContent = 'Analyzing...';

  try {
    const response = await fetch(`${API_BASE_URL}/predict/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        review_text: reviewInput,
        model_name: modelSelect
      })
    });

    if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
    const data = await response.json();

    const sentiment = data.prediction || 'Unknown';
    const confidence = data.confidence_score !== undefined 
      ? `${(data.confidence_score * 100).toFixed(1)}%` 
      : 'N/A';
    const isPos = sentiment.toLowerCase() === 'positive';

    resultSentiment.textContent = sentiment;
    resultSentiment.className = `badge ${isPos ? 'positive' : 'negative'}`;
    resultConfidence.textContent = `Confidence: ${confidence}`;
    
    resultContainer.classList.remove('hidden');
    document.getElementById('review-input').value = '';
  } catch (error) {
    console.error('Error processing prediction:', error);
    alert('Failed to connect to Django backend. Make sure the server is running on port 8000.');
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Analyze Sentiment';
  }
});

// Fetch MLflow Experiment Runs & Render Chart
document.getElementById('refresh-metrics-btn').addEventListener('click', fetchExperimentMetrics);

async function fetchExperimentMetrics() {
  const tableBody = document.getElementById('metrics-table-body');
  tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text">Loading MLflow runs...</td></tr>`;

  try {
    const response = await fetch(`${API_BASE_URL}/experiments/`);
    if (!response.ok) throw new Error(`HTTP Error: ${response.status}`);
    
    const experiments = await response.json();
    tableBody.innerHTML = '';

    if (experiments.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text">No experiment runs logged yet.</td></tr>`;
      return;
    }

    const labels = [];
    const accuracyScores = [];

    experiments.forEach((exp) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>${exp.model_name}</strong></td>
        <td class="metric-value">${(exp.accuracy * 100).toFixed(2)}%</td>
        <td class="metric-value">${(exp.f1_score * 100).toFixed(2)}%</td>
      `;
      tableBody.appendChild(row);

      labels.push(exp.model_name);
      accuracyScores.push((exp.accuracy * 100).toFixed(1));
    });

    renderMetricsChart(labels, accuracyScores);
  } catch (error) {
    console.error('Error fetching experiment metrics:', error);
    tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text error">Failed to load metrics. Check Django API connection.</td></tr>`;
  }
}

// Optional Chart.js Render Function
function renderMetricsChart(labels, data) {
  const ctx = document.getElementById('metricsChart').getContext('2d');
  if (metricsChartInstance) {
    metricsChartInstance.destroy();
  }

  metricsChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Accuracy (%)',
        data: data,
        backgroundColor: '#0056b3'
      }]
    },
    options: {
      responsive: true,
      scales: {
        y: { beginAtZero: true, max: 100 }
      }
    }
  });
}