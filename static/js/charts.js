// Chart.js helpers. Data comes from MySQL (via Flask) as JSON in <script id="chart-data">.
const COL = { brand: '#4f46e5', green: '#16a34a', red: '#dc2626', amber: '#f59e0b', sky: '#0ea5e9', grey: '#e2e8f0' };
const chartData = () => JSON.parse(document.getElementById('chart-data').textContent);
const monthName = m => { const [y, mo] = m.split('-'); return new Date(y, mo - 1).toLocaleString('en', { month: 'short', year: 'numeric' }); };
const pctAxis = { beginAtZero: true, max: 100, ticks: { callback: v => v + '%' } };
const barColor = (p, min) => p >= min ? COL.green : COL.red;

// draws the big % in the middle of a doughnut
const centerText = { id: 'centerText', afterDraw(chart, _a, opts) {
  if (!opts.text) return;
  const { ctx, chartArea: { left, right, top, bottom } } = chart;
  ctx.save(); ctx.font = 'bold 26px Segoe UI'; ctx.fillStyle = '#1e293b';
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(opts.text, (left + right) / 2, (top + bottom) / 2); ctx.restore();
} };

function doughnutOverall(id, value, min) {
  new Chart(document.getElementById(id), { type: 'doughnut', plugins: [centerText],
    data: { labels: ['Attendance', 'Remaining'], datasets: [{ data: [value, Math.max(0, 100 - value)],
      backgroundColor: [value >= min ? COL.green : COL.red, COL.grey], borderWidth: 0 }] },
    options: { maintainAspectRatio: false, cutout: '72%', plugins: { legend: { display: false }, centerText: { text: value + '%' } } } });
}

function subjectBar(id, subjects, min) {
  new Chart(document.getElementById(id), { data: {
    labels: subjects.map(s => s.subject_code),
    datasets: [
      { type: 'bar', label: 'Attendance %', data: subjects.map(s => s.pct), backgroundColor: subjects.map(s => barColor(s.pct, min)), borderRadius: 6 },
      { type: 'line', label: `Minimum (${min}%)`, data: subjects.map(() => min), borderColor: COL.amber, borderDash: [6, 4], pointRadius: 0 } ] },
    options: { maintainAspectRatio: false, scales: { y: pctAxis },
      plugins: { tooltip: { callbacks: { title: i => subjects[i[0].dataIndex].subject_name } } } } });
}

function trendLine(id, monthly, min) {
  new Chart(document.getElementById(id), { type: 'line', data: {
    labels: monthly.map(m => monthName(m.month)),
    datasets: [{ label: 'Attendance %', data: monthly.map(m => m.pct), borderColor: COL.brand, backgroundColor: 'rgba(79,70,229,.12)', fill: true, tension: .3, pointRadius: 4 },
               { label: `Minimum (${min}%)`, data: monthly.map(() => min), borderColor: COL.amber, borderDash: [6, 4], pointRadius: 0 }] },
    options: { maintainAspectRatio: false, scales: { y: pctAxis } } });
}

function presentAbsent(id, present, absent) {
  new Chart(document.getElementById(id), { type: 'pie', data: { labels: ['Present', 'Absent'],
    datasets: [{ data: [present, absent], backgroundColor: [COL.green, COL.red], borderWidth: 0 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } } });
}

function topLow(id, top, low, min) {
  const rows = [...top.map(s => ({ ...s, kind: 'Top' })), ...low.map(s => ({ ...s, kind: 'Low' }))];
  new Chart(document.getElementById(id), { type: 'bar', data: { labels: rows.map(r => r.name),
    datasets: [{ label: 'Attendance %', data: rows.map(r => r.pct), borderRadius: 5,
      backgroundColor: rows.map(r => r.kind === 'Top' ? COL.green : COL.red) }] },
    options: { indexAxis: 'y', maintainAspectRatio: false, scales: { x: pctAxis }, plugins: { legend: { display: false },
      tooltip: { callbacks: { afterLabel: c => rows[c.dataIndex].kind === 'Top' ? 'Top 5' : 'Lowest 5' } } } } });
}

function simpleBar(id, labels, values, label, color) {
  new Chart(document.getElementById(id), { type: 'bar', data: { labels,
    datasets: [{ label, data: values, backgroundColor: color || COL.brand, borderRadius: 6 }] },
    options: { maintainAspectRatio: false, scales: { y: pctAxis }, plugins: { legend: { display: false } } } });
}
