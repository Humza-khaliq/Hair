function toggleNav() {
    const navLinks = document.getElementById('nav-links');
    if (navLinks) {
        navLinks.classList.toggle('active');
    }
}

window.addEventListener('DOMContentLoaded', () => {
    document.body.classList.add('page-ready');
    initAmbientNetwork();
});

function initAmbientNetwork() {
    const canvas = document.getElementById('ambient-network');
    if (!canvas) {
        return;
    }

    const ctx = canvas.getContext('2d');
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const pointer = {
        x: window.innerWidth / 2,
        y: window.innerHeight / 2,
        active: false,
    };

    const config = {
        baseSpeed: 0.12,
        maxSpeed: 0.45,
        lineDistance: 150,
        pointerRadius: () => (window.innerWidth < 540 ? 180 : 260),
    };

    let particles = [];
    let rafId = null;
    let width = 0;
    let height = 0;
    let pixelRatio = Math.min(window.devicePixelRatio || 1, 2);

    const dotColor = 'rgba(93, 242, 255, 0.85)';
    const lineColor = (opacity) => `rgba(255, 209, 102, ${opacity})`;

    const clamp = (value, limit) => Math.max(Math.min(value, limit), -limit);

    function syncCanvasSize() {
        width = window.innerWidth;
        height = window.innerHeight;
        pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = width * pixelRatio;
        canvas.height = height * pixelRatio;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(pixelRatio, pixelRatio);
    }

    function particleCount() {
        const area = width * height;
        const count = Math.round(area / 16000);
        return Math.max(35, Math.min(120, count));
    }

    function createParticle() {
        const angle = Math.random() * Math.PI * 2;
        const speed = config.baseSpeed + Math.random() * (config.maxSpeed - config.baseSpeed);
        return {
            x: Math.random() * width,
            y: Math.random() * height,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            radius: 0.8 + Math.random() * 1.6,
        };
    }

    function rebuildParticles() {
        particles = Array.from({ length: particleCount() }, createParticle);
    }

    function updateParticle(particle) {
        particle.x += particle.vx;
        particle.y += particle.vy;

        if (particle.x <= 0 || particle.x >= width) {
            particle.vx *= -1;
            particle.x = Math.max(0, Math.min(width, particle.x));
        }

        if (particle.y <= 0 || particle.y >= height) {
            particle.vy *= -1;
            particle.y = Math.max(0, Math.min(height, particle.y));
        }

        if (pointer.active) {
            const dx = particle.x - pointer.x;
            const dy = particle.y - pointer.y;
            const distance = Math.hypot(dx, dy) || 1;
            const reach = config.pointerRadius();
            if (distance < reach) {
                const strength = (reach - distance) / reach;
                particle.vx += (dx / distance) * strength * 0.06;
                particle.vy += (dy / distance) * strength * 0.06;
            }
        }

        const limit = config.maxSpeed;
        particle.vx = clamp(particle.vx, limit);
        particle.vy = clamp(particle.vy, limit);
    }

    function drawConnections(particle, index) {
        for (let i = index + 1; i < particles.length; i += 1) {
            const other = particles[i];
            const dx = particle.x - other.x;
            const dy = particle.y - other.y;
            const distance = Math.hypot(dx, dy);

            if (distance < config.lineDistance) {
                const opacity = 0.05 + (1 - distance / config.lineDistance) * 0.25;
                ctx.strokeStyle = lineColor(opacity);
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(particle.x, particle.y);
                ctx.lineTo(other.x, other.y);
                ctx.stroke();
            }
        }
    }

    function drawNetwork(skipMotion = false) {
        ctx.clearRect(0, 0, width, height);

        particles.forEach((particle, index) => {
            if (!skipMotion) {
                updateParticle(particle);
            }

            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
            ctx.fillStyle = dotColor;
            ctx.fill();

            drawConnections(particle, index);
        });
    }

    function render() {
        drawNetwork(false);
        rafId = requestAnimationFrame(render);
    }

    function start() {
        if (!rafId) {
            rafId = requestAnimationFrame(render);
        }
    }

    function stop() {
        if (rafId) {
            cancelAnimationFrame(rafId);
            rafId = null;
        }
    }

    function handleResize() {
        syncCanvasSize();
        rebuildParticles();
        if (prefersReducedMotion.matches) {
            drawNetwork(true);
        }
    }

    syncCanvasSize();
    rebuildParticles();
    window.addEventListener('resize', handleResize);

    if (prefersReducedMotion.matches) {
        drawNetwork(true);
        return;
    }

    start();

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

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stop();
        } else {
            start();
        }
    });

    prefersReducedMotion.addEventListener('change', (event) => {
        if (event.matches) {
            stop();
            drawNetwork(true);
        } else {
            rebuildParticles();
            start();
        }
    });
}
