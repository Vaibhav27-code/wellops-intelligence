const fs = require('fs');
const path = require('path');
const puppeteer = require('../frontend/node_modules/puppeteer-core');

function mdToHtml(md) {
  const lines = md.split(/\r?\n/);
  let html = '';
  let inTable = false;
  let tableHeaderDone = false;
  let inList = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];

    // Page break
    if (line.includes('page-break-after: always') || line.includes('page-break') || line.includes('<!-- pagebreak -->')) {
      if (inList) { html += '</ul>\n'; inList = false; }
      if (inTable) { html += '</tbody></table>\n'; inTable = false; }
      html += '<div class="page-break"></div>\n';
      continue;
    }

    // Horizontal rule
    if (/^---$/.test(line.trim())) {
      if (inList) { html += '</ul>\n'; inList = false; }
      if (inTable) { html += '</tbody></table>\n'; inTable = false; }
      html += '<hr/>\n';
      continue;
    }

    // Table rows
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

    // Unordered list items
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) { html += '<ul>\n'; inList = true; }
      const content = line.replace(/^\s*[-*]\s+/, '');
      html += `<li>${formatInline(content)}</li>\n`;
      continue;
    } else if (inList && !/^\s+/.test(line) && line.trim() !== '') {
      html += '</ul>\n';
      inList = false;
    }

    // Headings
    if (line.startsWith('# ')) {
      html += `<h1>${formatInline(line.substring(2))}</h1>\n`;
      continue;
    }
    if (line.startsWith('## ')) {
      html += `<h2>${formatInline(line.substring(3))}</h2>\n`;
      continue;
    }
    if (line.startsWith('### ')) {
      html += `<h3>${formatInline(line.substring(4))}</h3>\n`;
      continue;
    }
    if (line.startsWith('#### ')) {
      html += `<h4>${formatInline(line.substring(5))}</h4>\n`;
      continue;
    }

    // Paragraph
    if (line.trim() === '') {
      continue;
    }
    html += `<p>${formatInline(line)}</p>\n`;
  }

  if (inList) html += '</ul>\n';
  if (inTable) html += '</tbody></table>\n';

  return html;
}

function formatInline(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\$([^\$]+)\$/g, '<span class="math">$1</span>');
}

async function exportPdf() {
  const mdPath = path.resolve(__dirname, 'writeup.md');
  const htmlPath = path.resolve(__dirname, 'writeup.html');
  const pdfPath = path.resolve(__dirname, 'writeup.pdf');

  const mdContent = fs.readFileSync(mdPath, 'utf8');
  const bodyHtml = mdToHtml(mdContent);

  const fullHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Asset Intelligence Copilot: Architecture & Evaluation Write-Up</title>
  <style>
    @page {
      size: A4 portrait;
      margin: 8mm 10mm 8mm 10mm;
    }
    * {
      box-sizing: border-box;
    }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.24;
      color: #111827;
      margin: 0;
      padding: 0;
    }
    h1 {
      font-size: 12.5pt;
      font-weight: 700;
      margin: 0 0 2px 0;
      color: #0f172a;
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
      font-size: 10pt;
      font-weight: 700;
      margin: 3px 0 1px 0;
      color: #0f172a;
    }
    p {
      margin: 0 0 2px 0;
    }
    hr {
      border: none;
      border-top: 1px solid #cbd5e1;
      margin: 2px 0 3px 0;
    }
    ul {
      margin: 1px 0 2px 0;
      padding-left: 14px;
    }
    li {
      margin-bottom: 1px;
    }
    code {
      font-family: Consolas, Monaco, monospace;
      font-size: 8.5pt;
      background: #f1f5f9;
      padding: 0 2px;
      border-radius: 2px;
    }
    .math {
      font-family: "Cambria Math", "Times New Roman", serif;
      font-style: italic;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 8pt;
      line-height: 1.15;
      margin: 2px 0 3px 0;
    }
    th, td {
      border: 1px solid #cbd5e1;
      padding: 1.5px 3px;
      text-align: left;
    }
    th {
      background-color: #f1f5f9;
      font-weight: 700;
    }
    tr:nth-child(even) td {
      background-color: #f8fafc;
    }
    .page-break {
      page-break-after: always;
      break-after: page;
      height: 0;
      margin: 0;
      padding: 0;
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
      top: '8mm',
      bottom: '8mm',
      left: '10mm',
      right: '10mm'
    }
  });

  await browser.close();
  console.log('Generated PDF:', pdfPath);

  // Check page count from PDF binary
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
