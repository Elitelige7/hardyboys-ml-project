// 1. Centralized Backend URL configuration to accommodate Option 1
// Change this to your live deployment URL or 'http://127.0.0.1:8000' during local testing
const BACKEND_URL = ''; 

document.getElementById('review-form').addEventListener('submit', async (e) => {
  e.preventDefault();

  const reviewInput = document.getElementById('review-text');
  const submitBtn = document.getElementById('submit-btn');
  const resultContainer = document.getElementById('result-container');

  const reviewText = reviewInput.value.trim();
  if (!reviewText) return;

  // UI loading state
  submitBtn.disabled = true;
  submitBtn.textContent = 'Analyzing...';

  try {
    // Send POST request to backend inference endpoint with dynamic URL routing
    const response = await fetch(`${BACKEND_URL}/api/predict/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ review: reviewText }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    
    // Hand off response payload to Step 2 display handler
    renderPredictionResult(data);

  } catch (error) {
    console.error('Submission failed:', error);
    resultContainer.innerHTML = `<p class="error" style="color: red;">Error processing request. Please ensure the Django backend is running.</p>`;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Analyze Sentiment';
  }
});

// Dynamic display handler for backend prediction response
function renderPredictionResult(data) {
  const resultContainer = document.getElementById('result-container');

  // Expecting response structure like: { prediction: "Positive", confidence: 0.94 }
  const sentiment = data.prediction || 'Unknown';
  const confidence = data.confidence ? (data.confidence * 100).toFixed(1) : null;

  // Determine badge styling based on sentiment value
  const isPositive = sentiment.toLowerCase() === 'positive';
  const badgeClass = isPositive ? 'positive' : 'negative';

  // Render the prediction card into the DOM
  resultContainer.innerHTML = `
    <div class="result-card">
      <h3 class="result-header">Predicted Sentiment:</h3>
      <span class="badge ${badgeClass}">${sentiment}</span>
      ${confidence ? `<p class="confidence-text">Model Confidence: <strong>\${confidence}%</strong></p>` : ''}
    </div>
  `;
}

document.getElementById('refresh-metrics-btn').addEventListener('click', fetchExperimentMetrics);

async function fetchExperimentMetrics() {
  const tableBody = document.getElementById('metrics-table-body');
  tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text">Loading metrics...</td></tr>`;

  try {
    // GET request to retrieve experiment metrics logged by backend
    const response = await fetch(`${BACKEND_URL}/api/experiments/`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    renderMetricsTable(data);

  } catch (error) {
    console.error('Failed to fetch metrics:', error);
    tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text" style="color: red;">Error loading experiment metrics. Check backend connectivity.</td></tr>`;
  }
}

function renderMetricsTable(experiments) {
  const tableBody = document.getElementById('metrics-table-body');
  
  if (!experiments || experiments.length === 0) {
    tableBody.innerHTML = `<tr><td colspan="3" class="placeholder-text">No experiment runs found.</td></tr>`;
    return;
  }

  // Clear existing table content
  tableBody.innerHTML = '';

  // Append rows for Naive Bayes and Logistic Regression
  experiments.forEach((exp) => {
    const row = document.createElement('tr');
    
    // Adjusted metric calculations to gracefully handle standard fractional floats from database
    const accuracyPct = (exp.accuracy * 100).toFixed(2) + '%';
    const f1Pct = (exp.f1_score * 100).toFixed(2) + '%';

    row.innerHTML = `
      <td><strong>${exp.model_name}</strong></td>
      <td class="metric-value">${accuracyPct}</td>
      <td class="metric-value">${f1Pct}</td>
    `;
    
    tableBody.appendChild(row);
  });
}
