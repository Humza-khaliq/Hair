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

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (prefersReducedMotion.matches) {
        canvas.remove();
        return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        return;
    }

    const pointer = { x: 0, y: 0, active: false };
    let width = window.innerWidth;
    let height = window.innerHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, 2);
    let animationFrame = null;
    const nodes = [];

    function setCanvasSize() {
        width = window.innerWidth;
        height = window.innerHeight;
        dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);
    }

    function targetCount() {
        if (width < 540) return 30;
        if (width < 1024) return 50;
        return 70;
    }

    function seedNodes() {
        nodes.length = 0;
        const count = targetCount();
        for (let i = 0; i < count; i += 1) {
            nodes.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * 0.25,
                vy: (Math.random() - 0.5) * 0.25,
                radius: Math.random() * 1.2 + 0.4,
            });
        }
    }

    function clampVelocity(value) {
        const limit = 0.45;
        return Math.max(Math.min(value, limit), -limit);
    }

    function updateNodes() {
        const pointerRadius = window.innerWidth < 540 ? 140 : 220;
        nodes.forEach((node) => {
            node.x += node.vx;
            node.y += node.vy;

            if (node.x <= 0 || node.x >= width) {
                node.vx *= -1;
            }
            if (node.y <= 0 || node.y >= height) {
                node.vy *= -1;
            }

            node.vx = clampVelocity(node.vx);
            node.vy = clampVelocity(node.vy);

            if (pointer.active) {
                const dx = node.x - pointer.x;
                const dy = node.y - pointer.y;
                const dist = Math.hypot(dx, dy) || 0.001;
                if (dist < pointerRadius) {
                    const strength = (pointerRadius - dist) / pointerRadius;
                    const pull = 0.2;
                    node.vx += (dx / dist) * strength * pull;
                    node.vy += (dy / dist) * strength * pull;
                }
            }
        });
    }

    function drawNodes() {
        ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
        nodes.forEach((node) => {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius, 0, Math.PI * 2);
            ctx.fill();
        });
    }

    function drawConnections() {
        const linkDistance = window.innerWidth < 768 ? 110 : 150;
        for (let i = 0; i < nodes.length; i += 1) {
            for (let j = i + 1; j < nodes.length; j += 1) {
                const dx = nodes[i].x - nodes[j].x;
                const dy = nodes[i].y - nodes[j].y;
                const dist = Math.hypot(dx, dy);
                if (dist < linkDistance) {
                    const alpha = 0.36 * (1 - dist / linkDistance);
                    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha.toFixed(3)})`;
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.moveTo(nodes[i].x, nodes[i].y);
                    ctx.lineTo(nodes[j].x, nodes[j].y);
                    ctx.stroke();
                }
            }
        }
    }

    function render() {
        ctx.clearRect(0, 0, width, height);
        updateNodes();
        drawConnections();
        drawNodes();
        animationFrame = requestAnimationFrame(render);
    }

    function start() {
        if (animationFrame) {
            cancelAnimationFrame(animationFrame);
        }
        render();
    }

    setCanvasSize();
    seedNodes();
    start();

    window.addEventListener('resize', () => {
        setCanvasSize();
        seedNodes();
    });

    window.addEventListener('pointermove', (event) => {
        pointer.x = event.clientX;
        pointer.y = event.clientY;
        pointer.active = true;
    });

    window.addEventListener('pointerleave', () => {
        pointer.active = false;
    });

    window.addEventListener('touchend', () => {
        pointer.active = false;
    });

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            cancelAnimationFrame(animationFrame);
            animationFrame = null;
        } else {
            start();
        }
    });
}
