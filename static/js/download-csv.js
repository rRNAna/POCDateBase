document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('btn-download-csv');
  const table = document.getElementById('spec-cpu2017');

  if (!btn || !table) return;

  btn.addEventListener('click', () => {
    // 1) 遍历表头
    const rows = Array.from(table.querySelectorAll('tr'));
    const csv = rows.map(tr => {
      const cells = Array.from(tr.querySelectorAll('th,td'));
      return cells.map(cell => {
        // 把单元格中的逗号、换行、双引号转义
        let text = cell.innerText.trim().replace(/"/g, '""');
        if (text.search(/("|,|\n)/g) >= 0) {
          text = `"${text}"`;
        }
        return text;
      }).join(',');
    }).join('\r\n');

    // 2) 构造下载链接
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${document.title || 'table'}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
});