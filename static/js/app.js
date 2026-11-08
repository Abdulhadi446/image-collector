/* Vista Cars — header state, scroll reveals, and the lightbox. */
(() => {
  "use strict";

  const root = document.documentElement;
  const head = document.getElementById("siteHead");
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* sticky header state --------------------------------------------------- */
  const syncHead = () => {
    if (head) head.classList.toggle("is-scrolled", window.scrollY > 24);
  };
  syncHead();
  window.addEventListener("scroll", syncHead, { passive: true });

  /* scroll reveals -------------------------------------------------------- */
  const revealItems = document.querySelectorAll(".reveal");
  if (!reduceMotion && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-in");
          io.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -7% 0px", threshold: 0.08 }
    );
    revealItems.forEach((item) => io.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-in"));
  }

  /* lightbox -------------------------------------------------------------- */
  const dataNode = document.getElementById("gallery-data");
  const lightbox = document.getElementById("lightbox");
  if (!dataNode || !lightbox) return;

  let frames = [];
  try {
    frames = JSON.parse(dataNode.textContent) || [];
  } catch (error) {
    frames = [];
  }
  if (!frames.length) return;

  const image = lightbox.querySelector("[data-lb-img]");
  const counter = lightbox.querySelector("[data-lb-count]");
  const name = lightbox.querySelector("[data-lb-name]");
  const caption = lightbox.querySelector("[data-lb-caption]");
  const download = lightbox.querySelector("[data-lb-download]");
  const closeBtn = lightbox.querySelector("[data-lb-close]");
  const prevBtn = lightbox.querySelector("[data-lb-prev]");
  const nextBtn = lightbox.querySelector("[data-lb-next]");
  let index = 0;
  let lastFocus = null;

  const pad = (value) => String(value).padStart(2, "0");

  const render = (nextIndex) => {
    index = (nextIndex + frames.length) % frames.length;
    const frame = frames[index];
    image.src = frame.url;
    image.alt = frame.alt || "";
    counter.textContent = `${pad(index + 1)} / ${pad(frames.length)}`;
    if (name) name.textContent = frame.filename;
    if (caption) {
      const dims = frame.width && frame.height ? `${frame.width} × ${frame.height}` : "";
      caption.textContent = [frame.alt, dims].filter(Boolean).join(" — ");
    }
    if (download) {
      download.href = frame.url;
      download.setAttribute("download", frame.filename);
    }
    // light preloading of the neighbours keeps arrow keys instant
    [frames[(index + 1) % frames.length], frames[(index - 1 + frames.length) % frames.length]]
      .forEach((neighbour) => {
        const preload = new Image();
        preload.src = neighbour.url;
      });
  };

  const open = (nextIndex) => {
    lastFocus = document.activeElement;
    render(nextIndex);
    lightbox.hidden = false;
    document.body.classList.add("no-scroll");
    closeBtn.focus({ preventScroll: true });
  };

  const close = () => {
    lightbox.hidden = true;
    document.body.classList.remove("no-scroll");
    image.removeAttribute("src");
    if (lastFocus && typeof lastFocus.focus === "function") {
      lastFocus.focus({ preventScroll: true });
    }
  };

  document.querySelectorAll("[data-open-frame]").forEach((trigger) => {
    trigger.addEventListener("click", () => open(Number(trigger.dataset.openFrame) || 0));
  });

  prevBtn.addEventListener("click", () => render(index - 1));
  nextBtn.addEventListener("click", () => render(index + 1));
  closeBtn.addEventListener("click", close);
  download.addEventListener("click", (event) => event.stopPropagation());

  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox || event.target.classList.contains("lightbox__stage")) {
      close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (lightbox.hidden) return;
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      render(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      render(index + 1);
    }
  });

  // swipe on touch devices
  let touchStartX = null;
  lightbox.addEventListener(
    "touchstart",
    (event) => {
      touchStartX = event.changedTouches[0]?.clientX ?? null;
    },
    { passive: true }
  );
  lightbox.addEventListener(
    "touchend",
    (event) => {
      if (touchStartX === null) return;
      const delta = (event.changedTouches[0]?.clientX ?? touchStartX) - touchStartX;
      if (Math.abs(delta) > 48) render(index + (delta < 0 ? 1 : -1));
      touchStartX = null;
    },
    { passive: true }
  );

  // keep the reveal observer from fighting the opening animation
  root.classList.add("has-lightbox");
})();
