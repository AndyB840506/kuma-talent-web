// "Signal from noise": wave lines, chaotic at the top, collapsing into one clean signal as the
// page scrolls. The pointer stirs nearby lines. Nothing on the page depends on this canvas.
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var cv = document.getElementById('field');
  var ctx = cv.getContext && cv.getContext('2d');
  if (!ctx) return;
  var W = 0, H = 0, dpr = Math.min(window.devicePixelRatio || 1, 1.5), LINES = 34, STEP = 14;
  var px = -9999, py = -9999, ex = -9999, ey = -9999, pulse = 0, progress = 0, shown = 0;
  function size() {
    W = cv.clientWidth; H = cv.clientHeight;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    LINES = W < 760 ? 22 : 34; STEP = W < 760 ? 10 : 14;
  }
  size(); window.addEventListener('resize', size);
  window.addEventListener('pointermove', function (e) { px = e.clientX; py = e.clientY; }, { passive: true });
  window.addEventListener('pointerdown', function (e) {
    px = e.clientX; py = e.clientY; pulse = 1;
    if (reduce || e.target.closest('input, select, textarea, label, button')) return;
    var r = document.createElement('span'); r.className = 'ripple';
    r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px';
    document.body.appendChild(r); setTimeout(function () { r.remove(); }, 950);
  }, { passive: true });
  function readProgress() {
    var max = Math.max(1, document.documentElement.scrollHeight - innerHeight);
    progress = Math.min(1, Math.max(0, scrollY / (max * 0.35)));
  }
  window.addEventListener('scroll', readProgress, { passive: true }); readProgress();
  var top = document.querySelector('header.top');
  function headerState() { top.classList.toggle('scrolled', scrollY > 40); }
  window.addEventListener('scroll', headerState, { passive: true }); headerState();
  function n(x, t, k) {
    return Math.sin(x * 0.011 + t * 0.9 + k * 1.7) * 0.55 + Math.sin(x * 0.027 - t * 1.3 + k * 4.1) * 0.3 + Math.sin(x * 0.061 + t * 2.1 + k * 7.3) * 0.15;
  }
  function beat(x, c) {
    var d = (x - c) / 26;
    return -Math.exp(-d * d) * 46 + Math.exp(-((d - 1.1) * (d - 1.1)) * 2.2) * 18;
  }
  var t0 = performance.now();
  function frame(now) {
    var t = reduce ? 0 : (now - t0) / 1000;
    shown += (progress - shown) * 0.06;
    ex += (px - ex) * 0.12; ey += (py - ey) * 0.12; pulse *= 0.94;
    var calm = shown, chaos = 1 - calm, mid = H * 0.5;
    ctx.clearRect(0, 0, W, H);
    for (var k = 0; k < LINES; k++) {
      var spread = (k / (LINES - 1) - 0.5) * H * 0.9 * chaos;
      var isSignal = k === Math.floor(LINES / 2);
      var a = isSignal ? 0.22 + calm * 0.55 : 0.05 + 0.1 * chaos;
      ctx.beginPath();
      for (var x = -STEP; x <= W + STEP; x += STEP) {
        var amp = (26 + 38 * chaos) * (isSignal ? 0.35 + 0.65 * chaos : 1);
        var y = mid + spread + n(x, t, k) * amp * (0.25 + chaos);
        if (isSignal) y += beat(x, W * 0.5) * (0.25 + 0.75 * calm);
        var dx = x - ex, dy = y - ey, dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < 180) y += Math.sin(dist * 0.08 - t * 6) * (1 - dist / 180) * (14 + 30 * pulse);
        if (x === -STEP) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = isSignal ? 'rgba(143,209,158,' + a.toFixed(3) + ')' : 'rgba(241,235,227,' + a.toFixed(3) + ')';
      ctx.lineWidth = isSignal ? 1.4 : 1;
      ctx.stroke();
    }
    if (!reduce) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
  if (reduce) window.addEventListener('scroll', function () { shown = progress; requestAnimationFrame(frame); }, { passive: true });
})();
