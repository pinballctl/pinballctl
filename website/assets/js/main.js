(function () {
  const navLinks = Array.from(document.querySelectorAll('.nav-link'));
  const sections = Array.from(document.querySelectorAll('main section[id]'));
  const nav = document.querySelector('.site-nav');
  const menuToggle = document.querySelector('.menu-toggle');

  const modal = document.getElementById('img-modal');
  const modalImg = modal?.querySelector('.img-modal__img');
  const modalClose = modal?.querySelector('.img-modal__close');

  function closeMenu() {
    nav?.classList.remove('open');
    menuToggle?.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('menu-open');
  }

  function closeModal() {
    if (!modal || !modalImg) return;
    modal.classList.remove('open');
    modal.setAttribute('aria-hidden', 'true');
    modalImg.src = '';
  }

  function openModal(src) {
    if (!modal || !modalImg || !src) return;
    modalImg.src = src;
    modal.classList.add('open');
    modal.setAttribute('aria-hidden', 'false');
  }

  menuToggle?.addEventListener('click', () => {
    const isOpen = nav?.classList.toggle('open');
    menuToggle?.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    document.body.classList.toggle('menu-open', !!isOpen);
  });

  navLinks.forEach((link) => {
    link.addEventListener('click', (e) => {
      const href = link.getAttribute('href') || '';
      if (!href.startsWith('#')) return;
      const target = document.querySelector(href);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      closeMenu();
    });
  });

  function setActiveNavById(id) {
    if (!id) return;
    navLinks.forEach((link) => {
      link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
    });
  }

  function updateActiveNavOnScroll() {
    if (!sections.length || !navLinks.length) return;
    const headerOffset = 96;
    const probe = window.scrollY + headerOffset + (window.innerHeight * 0.2);
    let current = sections[0];
    for (const section of sections) {
      if (section.offsetTop <= probe) current = section;
      else break;
    }
    const id = current?.getAttribute('id') || '';
    if (id) setActiveNavById(id);
  }

  if (sections.length && navLinks.length) {
    updateActiveNavOnScroll();
    window.addEventListener('scroll', updateActiveNavOnScroll, { passive: true });
    window.addEventListener('resize', updateActiveNavOnScroll);
    window.addEventListener('hashchange', () => {
      const id = (window.location.hash || '').replace(/^#/, '');
      if (id) setActiveNavById(id);
      else updateActiveNavOnScroll();
    });
  }

  document.querySelectorAll('.shot-click').forEach((node) => {
    node.addEventListener('click', () => {
      openModal(node.getAttribute('data-full'));
    });
  });

  modalClose?.addEventListener('click', closeModal);
  modal?.addEventListener('click', (e) => {
    if (e.target === modal || e.target.classList.contains('img-modal__backdrop')) {
      closeModal();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      closeModal();
      closeMenu();
    }
  });

  document.addEventListener('click', (e) => {
    if (!nav || !menuToggle) return;
    const target = e.target;
    if (!(target instanceof Element)) return;
    if (!nav.classList.contains('open')) return;
    if (nav.contains(target) || menuToggle.contains(target)) return;
    closeMenu();
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 920) {
      closeMenu();
    }
    updateActiveNavOnScroll();
  });
})();
