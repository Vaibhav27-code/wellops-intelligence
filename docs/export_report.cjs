const fs = require('fs');
const path = require('path');
const puppeteer = require('../frontend/node_modules/puppeteer-core');

function formatInline(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function mdToHtml(md) {
  const lines = md.split(/\r?\n/);
  let html = '';
  let inTable = false;
  let tableHeaderDone = false;
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    if (/^## Page \d+:/.test(line.trim())) {
      if (inList) { html += '</ul>\n'; inList = false; }
      if (inTable) { html += '</tbody></table>\n'; inTable = false; }
      html += '<div class="page-break"></div>\n';
      html += `<h2>${formatInline(line.replace(/^##\s*/, ''))}</h2>\n`;
      continue;
    }

    if (/^---$/.test(line.trim())) {
      if (inList) { html += '</ul>\n'; inList = false; }
      if (inTable) { html += '</tbody></table>\n'; inTable = false; }
      html += '<hr/>\n';
      continue;
    }

    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      if (inList) { html += '</ul>\n'; inList = false; }
      const cells = line.split('|').slice(1, -1).map(c => c.trim());
      if (cells.every(c => /^:?-+:?$/.test(c))) {
        tableHeaderDone = true;
        html += '<tbody>\n';
        continue;
      }
      if (!inTable) {
        inTable = true;
        tableHeaderDone = false;
        html += '<table>\n<thead>\n<tr>';
        cells.forEach(c => { html += `<th>${formatInline(c)}</th>`; });
        html += '</tr>\n</thead>\n';
      } else if (!tableHeaderDone) {
        html += '<tr>';
        cells.forEach(c => { html += `<th>${formatInline(c)}</th>`; });
        html += '</tr>\n';
      } else {
        html += '<tr>';
        cells.forEach(c => { html += `<td>${formatInline(c)}</td>`; });
        html += '</tr>\n';
      }
      continue;
    } else if (inTable) {
      html += '</tbody></table>\n';
      inTable = false;
    }

    if (/^#{1}\s+(.*)/.test(line)) {
      if (inList) { html += '</ul>\n'; inList = false; }
      html += `<h1>${formatInline(line.replace(/^#{1}\s+/, ''))}</h1>\n`;
      continue;
    }
    if (/^#{2}\s+(.*)/.test(line)) {
      if (inList) { html += '</ul>\n'; inList = false; }
      html += `<h2>${formatInline(line.replace(/^#{2}\s+/, ''))}</h2>\n`;
      continue;
    }
    if (/^#{3}\s+(.*)/.test(line)) {
      if (inList) { html += '</ul>\n'; inList = false; }
      html += `<h3>${formatInline(line.replace(/^#{3}\s+/, ''))}</h3>\n`;
      continue;
    }
    if (/^#{4}\s+(.*)/.test(line)) {
      if (inList) { html += '</ul>\n'; inList = false; }
      html += `<h4>${formatInline(line.replace(/^#{4}\s+/, ''))}</h4>\n`;
      continue;
    }

    if (/^[\*\-]\s+(.*)/.test(line.trim())) {
      const content = line.trim().replace(/^[\*\-]\s+/, '');
      if (!inList) {
        inList = true;
        html += '<ul>\n';
      }
      html += `  <li>${formatInline(content)}</li>\n`;
      continue;
    } else if (inList && line.trim() === '') {
      html += '</ul>\n';
      inList = false;
    }

    if (line.trim() === '') {
      continue;
    }

    html += `<p>${formatInline(line)}</p>\n`;
  }

  if (inTable) html += '</tbody></table>\n';
  if (inList) html += '</ul>\n';
  return html;
}

async function exportPdf() {
  const mdPath = path.join(__dirname, 'report.md');
  const htmlPath = path.join(__dirname, 'report.html');
  const pdfPath = path.join(__dirname, 'report.pdf');

  const md = fs.readFileSync(mdPath, 'utf8');
  const bodyHtml = mdToHtml(md);

  const fullHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Asset Intelligence Copilot - Report</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 10mm 12mm 10mm 12mm;
    }
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 8.5pt;
      line-height: 1.25;
      color: #111;
      background: #fff;
      margin: 0;
      padding: 0;
    }
    .page-break {
      page-break-before: always;
      break-before: page;
      height: 0;
      margin: 0;
      border: none;
    }
    h1 {
      font-size: 13.5pt;
      font-weight: 700;
      margin: 0 0 2px 0;
      color: #0f172a;
      border-bottom: 1.5px solid #0f172a;
      padding-bottom: 2px;
    }
    h2 {
      font-size: 10.5pt;
      font-weight: 700;
      margin: 4px 0 2px 0;
      color: #1e293b;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 1px;
    }
    h3 {
      font-size: 9pt;
      font-weight: 700;
      margin: 3px 0 1px 0;
      color: #2563eb;
    }
    p {
      margin: 1px 0 2px 0;
    }
    ul {
      margin: 1px 0 2px 14px;
      padding: 0;
    }
    li {
      margin-bottom: 1px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 7.5pt;
      margin: 2px 0 3px 0;
    }
    th, td {
      border: 0.5px solid #cbd5e1;
      padding: 2px 4px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background-color: #f1f5f9;
      font-weight: 700;
    }
    code {
      font-family: ui-monospace, Menlo, Monaco, Consolas, monospace;
      font-size: 8pt;
      background: #f1f5f9;
      padding: 1px 2px;
      border-radius: 2px;
    }
    hr {
      border: none;
      border-top: 0.5px solid #e2e8f0;
      margin: 2px 0;
    }
  </style>
</head>
<body>
${bodyHtml}
</body>
</html>`;

  fs.writeFileSync(htmlPath, fullHtml, 'utf8');
  console.log('Generated:', htmlPath);

  const chromePath = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  await page.goto('file:///' + htmlPath.replace(/\\/g, '/'), { waitUntil: 'networkidle0' });

  await page.pdf({
    path: pdfPath,
    format: 'A4',
    printBackground: true,
    margin: {
      top: '6mm',
      bottom: '6mm',
      left: '8mm',
      right: '8mm'
    }
  });

  await browser.close();
  console.log('Generated PDF:', pdfPath);

  const pdfBuffer = fs.readFileSync(pdfPath);
  const pdfString = pdfBuffer.toString('binary');
  const matches = pdfString.match(/\/Type\s*\/Page\b/g);
  const count = matches ? matches.length : 0;
  console.log('Rendered PDF Page Count:', count);
  return count;
}

exportPdf().catch(err => {
  console.error('Error during export:', err);
  process.exit(1);
});
