document.body.addEventListener('htmx:afterSwap', (event) => {
  if (event.target && event.target.id === 'chat-log') {
    event.target.scrollTop = event.target.scrollHeight;
  }
});

document.addEventListener('DOMContentLoaded', () => {
  const docSelect = document.getElementById('chat-document-id');
  const workspaceDocId = document.getElementById('workspace-document-id');

  const syncDocumentContext = () => {
    if (docSelect && workspaceDocId) {
      workspaceDocId.value = docSelect.value || '';
    }
  };
  syncDocumentContext();
  if (docSelect) {
    docSelect.addEventListener('change', syncDocumentContext);
  }

  const chatForms = document.querySelectorAll('form[data-chat-form="true"]');
  chatForms.forEach((form) => {
    const textarea = form.querySelector('textarea[name="user_prompt"]');
    const submitButton = form.querySelector('button[type="submit"]');
    const status = document.getElementById('chat-status');

    if (textarea) {
      textarea.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
          event.preventDefault();
          form.requestSubmit();
        }
      });
    }

    form.addEventListener('submit', () => {
      if (status) {
        status.textContent = '답변 생성 중...';
      }
      if (submitButton) {
        submitButton.disabled = true;
      }
    });
  });

  const generateForms = document.querySelectorAll('form[data-generate-form="true"]');
  generateForms.forEach((form) => {
    const submitButton = form.querySelector('button[type="submit"]');
    const statusTargetSelector = form.dataset.statusTarget;
    const status = statusTargetSelector ? document.querySelector(statusTargetSelector) : null;
    form.addEventListener('submit', () => {
      if (status) {
        status.textContent = 'TC 생성 요청을 처리 중입니다...';
      }
      if (submitButton) {
        submitButton.disabled = true;
      }
    });
  });
});

document.body.addEventListener('htmx:responseError', (event) => {
  const form = event.detail.elt?.closest?.('form[data-chat-form="true"]');
  if (!form) {
    return;
  }
  const status = document.getElementById('chat-status');
  if (status) {
    status.textContent = `요청 실패: HTTP ${event.detail.xhr.status}`;
  }
  const submitButton = form.querySelector('button[type="submit"]');
  if (submitButton) {
    submitButton.disabled = false;
  }
});

document.body.addEventListener('htmx:afterRequest', (event) => {
  const form = event.detail.elt?.closest?.('form[data-chat-form="true"]');
  if (form) {
    const submitButton = form.querySelector('button[type="submit"]');
    const status = document.getElementById('chat-status');
    if (submitButton) {
      submitButton.disabled = false;
    }
    if (event.detail.successful) {
      form.reset();
      if (status) {
        status.textContent = '';
      }
    }
  }

  const generateForm = event.detail.elt?.closest?.('form[data-generate-form="true"]');
  if (generateForm) {
    const submitButton = generateForm.querySelector('button[type="submit"]');
    const statusTargetSelector = generateForm.dataset.statusTarget;
    const status = statusTargetSelector ? document.querySelector(statusTargetSelector) : null;
    if (submitButton) {
      submitButton.disabled = false;
    }
    if (status) {
      status.textContent = event.detail.successful
        ? '생성 응답 수신 완료. 아래 request_id/상태를 확인하세요.'
        : '생성 요청 실패. 잠시 후 다시 시도해 주세요.';
    }
  }
});
