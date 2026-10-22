// Fun Videos · Anna — small progressive enhancements. The page works without this file:
// videos still have posters, links still go to GitHub.
(() => {
  'use strict';

  // ---------- Players: poster cover → native controls on first play ----------

  function activate(player, autoplay) {
    const video = player.querySelector('video');
    player.classList.add('is-active');
    video.controls = true;
    if (autoplay) {
      const p = video.play();
      if (p && p.catch) p.catch(() => {}); // autoplay blocked → controls are already visible
    }
  }

  function reset(player) {
    const video = player.querySelector('video');
    player.classList.remove('is-active');
    video.controls = false;
  }

  document.querySelectorAll('[data-player]').forEach((player) => {
    const video = player.querySelector('video');
    player.querySelector('.player__cover').addEventListener('click', () => activate(player, true));
    video.addEventListener('ended', () => reset(player));
  });

  // Only one video plays at a time.
  document.addEventListener('play', (e) => {
    document.querySelectorAll('video').forEach((v) => {
      if (v !== e.target && !v.paused) v.pause();
    });
  }, true);

  // ---------- Version / source switches ----------

  document.querySelectorAll('.seg__btn[data-for]').forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.getAttribute('aria-pressed') === 'true') return;
      const player = document.getElementById(btn.dataset.for);
      const video = player.querySelector('video');
      const wasPlaying = !video.paused && !video.ended;

      btn.parentElement.querySelectorAll('.seg__btn').forEach((b) => {
        b.setAttribute('aria-pressed', String(b === btn));
      });

      video.pause();
      video.poster = btn.dataset.poster;
      video.src = btn.dataset.src;
      player.querySelector('[data-time]').textContent = btn.dataset.time;

      const caption = player.parentElement.querySelector('[data-viewer-cap]');
      if (caption && btn.dataset.caption) caption.textContent = btn.dataset.caption;

      if (wasPlaying) activate(player, true);
      else reset(player);
    });
  });

  // ---------- Lightbox for contact sheets ----------

  const dialog = document.querySelector('[data-lightbox-dialog]');
  if (dialog && typeof dialog.showModal === 'function') {
    const img = dialog.querySelector('[data-lightbox-img]');
    document.querySelectorAll('[data-lightbox]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const thumb = btn.querySelector('img');
        img.src = btn.dataset.src;
        img.alt = thumb ? thumb.alt : '';
        dialog.showModal();
      });
    });
    dialog.querySelector('[data-lightbox-close]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (e) => { if (e.target === dialog) dialog.close(); });
  } else {
    // No <dialog> support: open the image directly.
    document.querySelectorAll('[data-lightbox]').forEach((btn) => {
      btn.addEventListener('click', () => { window.location.href = btn.dataset.src; });
    });
  }

  // ---------- Top bar border + current section ----------

  const topbar = document.querySelector('[data-topbar]');
  const onScroll = () => topbar.classList.toggle('is-scrolled', window.scrollY > 8);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  if ('IntersectionObserver' in window) {
    const links = new Map();
    document.querySelectorAll('[data-nav]').forEach((a) => links.set(a.getAttribute('href').slice(1), a));
    const sections = [...links.keys()].map((id) => document.getElementById(id)).filter(Boolean);
    const spy = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        links.forEach((a, id) => a.classList.toggle('is-current', id === entry.target.id));
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    sections.forEach((s) => spy.observe(s));

    // Gentle reveal for the sections below the fold.
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!reduce) {
      const targets = document.querySelectorAll('.flow__steps, .case, .method-list');
      const reveal = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add('is-in');
          reveal.unobserve(entry.target);
        });
      }, { rootMargin: '0px 0px -8% 0px' });
      targets.forEach((t) => { t.classList.add('reveal'); reveal.observe(t); });
    }
  }
})();
