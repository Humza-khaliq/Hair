function toggleNav() {
    const navLinks = document.getElementById('nav-links');
    if (navLinks) {
        navLinks.classList.toggle('active');
    }
}

window.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('page-ready');
    initBarberAmbient();
});

function initBarberAmbient() {
    const container = document.querySelector('.barber-bg');
    if (!container) {
        return;
    }

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (prefersReducedMotion.matches) {
        container.classList.add('no-motion');
        return;
    }

    const tools = Array.from(container.querySelectorAll('.tool'));
    if (!tools.length) {
        return;
    }

    const pointer = {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
        active: false,
    };

    const states = tools.map((tool) => {
        const range = parseFloat(tool.dataset.floatRange || '24');
        const speed = parseFloat(tool.dataset.floatSpeed || '0.12');
        return {
            tool,
            range,
            vx: (Math.random() - 0.5) * speed,
            vy: (Math.random() - 0.5) * speed,
            offsetX: 0,
            offsetY: 0,
        };
    });

    const clamp = (value, limit) => Math.max(Math.min(value, limit), -limit);
    let rafId = null;

    const basePointerRadius = () => (window.innerWidth < 540 ? 220 : 380);

    function tick() {
        const pointerRadius = basePointerRadius();
        states.forEach((state) => {
            state.offsetX += state.vx;
            state.offsetY += state.vy;

            if (Math.abs(state.offsetX) > state.range) {
                state.vx *= -1;
            }
            if (Math.abs(state.offsetY) > state.range) {
                state.vy *= -1;
            }

            state.vx = clamp(state.vx, 1.2);
            state.vy = clamp(state.vy, 1.2);

            if (pointer.active) {
                const rect = state.tool.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                const dx = centerX - pointer.x;
                const dy = centerY - pointer.y;
                const dist = Math.hypot(dx, dy) || 1;
                if (dist < pointerRadius) {
                    const strength = (pointerRadius - dist) / pointerRadius;
                    const pull = 1; // matches previous ambient line sensitivity
                    state.vx += (dx / dist) * strength * pull;
                    state.vy += (dy / dist) * strength * pull;
                }
            }

            state.tool.style.setProperty('--float-x', `${state.offsetX}px`);
            state.tool.style.setProperty('--float-y', `${state.offsetY}px`);
        });

        rafId = requestAnimationFrame(tick);
    }

    function start() {
        if (!rafId) {
            rafId = requestAnimationFrame(tick);
        }
    }

    function stop() {
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = null;
        }
    }

    window.addEventListener('pointermove', (event) => {
        pointer.active = true;
        pointer.x = event.clientX;
        pointer.y = event.clientY;
    });

    window.addEventListener('pointerleave', () => {
        pointer.active = false;
    });

    window.addEventListener('touchend', () => {
        pointer.active = false;
    });

    window.addEventListener('resize', () => {
        pointer.x = window.innerWidth / 2;
        pointer.y = window.innerHeight / 2;
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stop();
        } else {
            start();
        }
    });

    start();
}
