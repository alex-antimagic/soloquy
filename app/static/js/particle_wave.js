// Particle Network Animation
// Modern particle network background with mouse interaction
// Grey/White/Blue color scheme

document.addEventListener('DOMContentLoaded', function() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let lastTime = 0;

    // Color palette - Grey/White/Blue shades
    const colors = {
        darkBlue: { r: 79, g: 109, b: 145 },      // #4f6d91
        mediumBlue: { r: 107, g: 142, b: 179 },   // #6b8eb3
        lightBlue: { r: 156, g: 183, b: 213 },    // #9cb7d5
        paleBlue: { r: 197, g: 213, b: 230 },     // #c5d5e6
        lightGrey: { r: 230, g: 234, b: 238 },    // #e6eaee
        white: { r: 248, g: 249, b: 250 }         // #f8f9fa
    };

    // Set canvas dimensions
    function setCanvasDimensions() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    setCanvasDimensions();
    window.addEventListener('resize', setCanvasDimensions);

    // Create particles
    const particles = [];
    const particleCount = 80;
    const keyParticleIndices = [];

    // Randomly select some particles to be "key" particles that light up
    for (let i = 0; i < Math.floor(particleCount * 0.2); i++) {
        keyParticleIndices.push(Math.floor(Math.random() * particleCount));
    }

    // Initialize particles
    for (let i = 0; i < particleCount; i++) {
        const isKeyParticle = keyParticleIndices.includes(i);

        particles.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            radius: isKeyParticle ? 4 : 3,
            color: colors.mediumBlue,
            originalColor: colors.mediumBlue,
            highlightColor: colors.white,
            velocityX: (Math.random() - 0.5) * 0.4,
            velocityY: (Math.random() - 0.5) * 0.4,
            isKeyParticle: isKeyParticle,
            isActive: false,
            activeTime: 0,
            activationInterval: 5000 + Math.random() * 10000,
            lastActivation: Math.random() * 5000,
            connections: []
        });
    }

    // Generate random connections for each particle
    particles.forEach((particle, index) => {
        const connectionCount = 3 + Math.floor(Math.random() * 3);
        for (let i = 0; i < connectionCount; i++) {
            let connectionIndex;
            do {
                connectionIndex = Math.floor(Math.random() * particleCount);
            } while (connectionIndex === index || particle.connections.includes(connectionIndex));
            particle.connections.push(connectionIndex);
        }
    });


    // Animation loop
    function animate(currentTime) {
        const deltaTime = currentTime - lastTime;
        lastTime = currentTime;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw connections first (behind particles)
        ctx.lineWidth = 0.8;
        particles.forEach(particle => {
            particle.connections.forEach(connectionIndex => {
                const connectedParticle = particles[connectionIndex];

                const dx = particle.x - connectedParticle.x;
                const dy = particle.y - connectedParticle.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const maxDistance = 180;

                if (distance < maxDistance) {
                    let opacity = 0.08 * (1 - distance / maxDistance);

                    // Increase opacity when either particle is active
                    if (particle.isActive || connectedParticle.isActive ||
                        particle.isKeyParticle || connectedParticle.isKeyParticle) {
                        opacity += 0.15;
                    }

                    ctx.beginPath();
                    ctx.moveTo(particle.x, particle.y);
                    ctx.lineTo(connectedParticle.x, connectedParticle.y);
                    ctx.strokeStyle = `rgba(${colors.lightBlue.r}, ${colors.lightBlue.g}, ${colors.lightBlue.b}, ${opacity})`;
                    ctx.stroke();
                }
            });
        });

        // Update and draw particles
        particles.forEach(particle => {
            // Update position
            particle.x += particle.velocityX;
            particle.y += particle.velocityY;

            // Boundary check with bounce
            if (particle.x < 0 || particle.x > canvas.width) {
                particle.velocityX *= -1;
                particle.x = Math.max(0, Math.min(canvas.width, particle.x));
            }
            if (particle.y < 0 || particle.y > canvas.height) {
                particle.velocityY *= -1;
                particle.y = Math.max(0, Math.min(canvas.height, particle.y));
            }

            // Update activation state for key particles
            if (particle.isKeyParticle) {
                particle.lastActivation += deltaTime;
                if (particle.lastActivation > particle.activationInterval) {
                    particle.isActive = !particle.isActive;
                    particle.lastActivation = 0;
                    particle.activeTime = 0;
                }

                if (particle.isActive) {
                    particle.activeTime += deltaTime;
                    if (particle.activeTime > 3000) {
                        particle.isActive = false;
                    }
                }
            }

            // Determine particle color
            let finalColor;
            if (particle.isActive) {
                // Pulsing animation for active particles
                const progress = Math.sin((currentTime % 2000) / 2000 * Math.PI) * 0.5 + 0.5;
                finalColor = {
                    r: particle.originalColor.r * (1 - progress) + colors.paleBlue.r * progress,
                    g: particle.originalColor.g * (1 - progress) + colors.paleBlue.g * progress,
                    b: particle.originalColor.b * (1 - progress) + colors.paleBlue.b * progress
                };
            } else if (particle.isKeyParticle) {
                finalColor = colors.lightBlue;
            } else {
                finalColor = colors.darkBlue;
            }

            // Draw particle
            ctx.beginPath();
            ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgb(${finalColor.r}, ${finalColor.g}, ${finalColor.b})`;
            ctx.fill();

            // Add glow effect for active particles
            if (particle.isActive || particle.isKeyParticle) {
                const glowRadius = particle.radius * 2.5;
                const gradient = ctx.createRadialGradient(
                    particle.x, particle.y, particle.radius,
                    particle.x, particle.y, glowRadius
                );
                gradient.addColorStop(0, `rgba(${finalColor.r}, ${finalColor.g}, ${finalColor.b}, 0.3)`);
                gradient.addColorStop(1, `rgba(${finalColor.r}, ${finalColor.g}, ${finalColor.b}, 0)`);

                ctx.beginPath();
                ctx.arc(particle.x, particle.y, glowRadius, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
            }
        });

        requestAnimationFrame(animate);
    }

    requestAnimationFrame(animate);
});
