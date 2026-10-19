"""Add one D3 chart below the existing dashboard table, with a backup first."""

from datetime import datetime
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "backend" / "index.html"
MARKER = "<!-- MLFlowPro: D3 experiment chart -->"

CHART_HTML = '''
    <!-- MLFlowPro: D3 experiment chart -->
    <section style="margin-top:24px;" aria-labelledby="experiment-chart-heading">
      <h3 id="experiment-chart-heading">Experiment history</h3>
      <label for="chart-metric">Chart metric:</label>
      <select id="chart-metric" style="padding:6px; margin:0 0 10px 6px;">
        <option value="both">Accuracy and macro F1</option>
        <option value="accuracy">Accuracy</option>
        <option value="f1_score">Macro F1</option>
      </select>
      <p style="font-size:13px; color:#666;">
        Up to six latest logged results. Run numbers identify experiments.
        Hover over a bar to see its score.
      </p>
      <div id="experiment-chart" aria-live="polite">
        Click "Load Experiment Metrics" to draw the chart.
      </div>
    </section>
'''

CHART_JS = r'''
    // MLFlowPro: D3 chart, using the same response as the existing metrics table.
    let experimentChartResults = [];

    function renderExperimentChart(results) {
      if (Array.isArray(results)) experimentChartResults = results;
      const host = document.getElementById('experiment-chart');
      host.replaceChildren();
      if (!window.d3) {
        host.textContent = 'Chart library could not load. Check your connection and refresh.';
        return;
      }

      const rows = experimentChartResults.filter(row =>
        [row.accuracy, row.f1_score].every(value =>
          typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
        )
      ).slice().sort((a, b) => {
        const timeA = Date.parse(a.created_at) || 0;
        const timeB = Date.parse(b.created_at) || 0;
        return timeB - timeA || Number(b.id || 0) - Number(a.id || 0);
      }).slice(0, 6);

      if (!rows.length) {
        host.textContent = 'No logged scores are available yet.';
        return;
      }
      const names = {
        logistic_regression: 'Logistic Regression',
        naive_bayes: 'Naive Bayes',
      };
      const nameOf = row => {
        const raw = String(row.model_name || 'Unknown model');
        return names[raw.trim().toLowerCase().replace(/[\s-]+/g, '_')] || raw;
      };
      const choice = document.getElementById('chart-metric').value;
      const metrics = [
        {key:'accuracy', label:'Accuracy', color:'#0056b3'},
        {key:'f1_score', label:'Macro F1', color:'#218838'},
      ].filter(metric => choice === 'both' || choice === metric.key);
      const width = 760;
      const left = 220;
      const right = 75;
      const top = 42;
      const rowHeight = 65;
      const height = top + rows.length * rowHeight + 35;
      const x = d3.scaleLinear().domain([0, 1]).range([left, width - right]);
      const svg = d3.select(host).append('svg')
        .attr('width', width).attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('role', 'img')
        .attr('aria-label', 'Logged accuracy and macro F1 by experiment run')
        .style('max-width', '100%').style('height', 'auto');

      metrics.forEach((metric, index) => {
        svg.append('rect').attr('x', left + index * 150).attr('y', 9)
          .attr('width', 12).attr('height', 12).attr('fill', metric.color);
        svg.append('text').attr('x', left + 18 + index * 150).attr('y', 19)
          .attr('font-size', 12).text(metric.label);
      });
      svg.append('g').attr('transform', `translate(0,${height - 29})`)
        .call(d3.axisBottom(x).ticks(5).tickFormat(d3.format('.0%')))
        .attr('font-size', 12);

      rows.forEach((row, index) => {
        const baseY = top + index * rowHeight;
        svg.append('text').attr('x', left - 12).attr('y', baseY + 20)
          .attr('text-anchor', 'end').attr('font-size', 12)
          .text(`${nameOf(row)} / Run ${row.experiment}`);
        metrics.forEach((metric, metricIndex) => {
          const value = row[metric.key];
          const y = baseY + metricIndex * 23;
          const label = `${nameOf(row)}, Run ${row.experiment}: ${metric.label} ${(value * 100).toFixed(2)}%`;
          svg.append('rect').attr('class', 'experiment-score-bar')
            .attr('data-result-id', row.id).attr('data-metric', metric.key)
            .attr('data-score', value)
            .attr('x', left).attr('y', y).attr('width', x(value) - left)
            .attr('height', 17).attr('rx', 2).attr('fill', metric.color)
            .attr('tabindex', 0).attr('aria-label', label)
            .append('title').text(label);
          svg.append('text').attr('x', x(value) + 7).attr('y', y + 13)
            .attr('font-size', 12).text(`${(value * 100).toFixed(2)}%`);
        });
      });
    }

    document.getElementById('chart-metric').addEventListener('change', () => renderExperimentChart());
'''


def main():
    if not PAGE.is_file():
        raise SystemExit("Place add_metrics_chart.py in the project root, beside train_models.py.")
    original = PAGE.read_text(encoding="utf-8")
    if MARKER in original:
        print("The chart is already installed. Refresh the page and load experiment metrics.")
        return

    table = re.search(r'<tbody\b[^>]*\bid=["\']metrics-table-body["\']', original)
    if not table:
        raise SystemExit("Could not find metrics-table-body. No changes made.")
    table_end = original.find("</table>", table.end())
    if table_end < 0:
        raise SystemExit("Could not find the end of the metrics table. No changes made.")

    # All edits are prepared in memory before the existing page is written.
    insertion = table_end + len("</table>")
    updated = original[:insertion] + CHART_HTML + original[insertion:]
    pattern = r'(?P<indent>^[ \t]*)const\s+experiments\s*=\s*await\s+response\.json\(\)\s*;'
    updated, count = re.subn(
        pattern,
        lambda match: match.group(0) + "\n" + match.group("indent") + "renderExperimentChart(experiments);",
        updated, flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit("Could not identify the existing metrics response. No changes made.")
    inline_script = re.search(r'<script\s*>', updated, flags=re.IGNORECASE)
    if not inline_script:
        raise SystemExit("Could not find the dashboard script. No changes made.")
    updated = (
        updated[:inline_script.start()]
        + '<script src="https://cdn.jsdelivr.net/npm/d3@7"></script>\n'
        + updated[inline_script.start():]
    )
    end_script = updated.lower().rfind("</script>")
    updated = updated[:end_script] + CHART_JS + "\n  " + updated[end_script:]

    folder = ROOT / "local_jobs" / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / f"index-before-chart-{datetime.now():%Y%m%d-%H%M%S-%f}.html"
    backup.write_bytes(PAGE.read_bytes())
    PAGE.write_text(updated, encoding="utf-8")
    print("Added the D3 chart below the existing metrics table.")
    print(f"Original page backup: {backup}")
    print("Refresh the local dashboard, then click Load Experiment Metrics.")


if __name__ == "__main__":
    main()
