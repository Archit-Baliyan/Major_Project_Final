// General page behaviour: confirmations, form validation, add/edit modal, attendance helpers.
document.addEventListener('DOMContentLoaded', () => {

  // 1. Confirmation before destructive actions: <form data-confirm="Are you sure?">
  document.querySelectorAll('form[data-confirm]').forEach(f =>
    f.addEventListener('submit', e => { if (!confirm(f.dataset.confirm)) e.preventDefault(); }));

  // 2. Bootstrap client-side validation (server-side validation is always done as well)
  document.querySelectorAll('form.needs-validation').forEach(f =>
    f.addEventListener('submit', e => {
      if (!f.checkValidity()) { e.preventDefault(); e.stopPropagation(); }
      f.classList.add('was-validated');
    }));

  // 3. One modal reused for "Add" and "Edit": buttons carry data-action, data-title, data-values
  const modal = document.getElementById('formModal');
  if (modal) modal.addEventListener('show.bs.modal', ev => {
    const btn = ev.relatedTarget, form = modal.querySelector('form');
    form.reset(); form.classList.remove('was-validated');
    form.action = btn.dataset.action;
    modal.querySelector('.modal-title').textContent = btn.dataset.title;
    const editing = !!btn.dataset.values;
    Object.entries(editing ? JSON.parse(btn.dataset.values) : {}).forEach(([k, v]) => {
      if (form.elements[k]) form.elements[k].value = v;
    });
    form.querySelectorAll('[data-pw-optional]').forEach(el => {
      el.required = !editing;
      el.placeholder = editing ? 'Leave blank to keep current password' : '';
    });
  });

  // 4. Attendance page: Mark All buttons + live counters
  const table = document.getElementById('attTable');
  if (table) {
    const count = () => {
      const p = table.querySelectorAll('input[value="Present"]:checked').length;
      const a = table.querySelectorAll('input[value="Absent"]:checked').length;
      document.getElementById('cntPresent').textContent = p;
      document.getElementById('cntAbsent').textContent = a;
    };
    document.querySelectorAll('[data-markall]').forEach(b => b.addEventListener('click', () => {
      table.querySelectorAll(`input[value="${b.dataset.markall}"]`).forEach(r => r.checked = true);
      count();
    }));
    table.addEventListener('change', count);
    count();
  }

  // 5. Auto-submit filter selects
  document.querySelectorAll('select[data-autosubmit]').forEach(s =>
    s.addEventListener('change', () => s.form.submit()));
});
