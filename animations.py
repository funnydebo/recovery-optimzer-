"""
Recovery Optimizer - Pure Offline Animated Components
=====================================================
Module: animations.py
Provides lightweight, offline HTML/Canvas/SVG animated components for Streamlit:
  - Hero Banner (layered open-pit silhouette, tumbling rocks, dust particles, copper glow)
  - Static fallback banners when "Reduce animations" is active
  - Zero external CDN dependencies; pure HTML5 canvas and inline CSS/SVG.
"""

def render_hero_banner(reduced_animations: bool = False) -> str:
    """
    Renders the Hero Banner at the top of the application.
    If reduced_animations is True, returns a clean static glass banner.
    If False, runs a high-performance 60fps canvas animation with pit benches,
    tumbling rock particles, and ambient copper dust.
    """
    if reduced_animations:
        return """
        <div style="
            background: linear-gradient(135deg, #131b2e 0%, #0d1322 100%);
            border: 1px solid rgba(217, 119, 54, 0.35);
            border-radius: 12px;
            padding: 24px 30px;
            margin-bottom: 24px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.5);
            display: flex;
            justify-content: space-between;
            align-items: center;
        ">
            <div>
                <div style="
                    display: inline-block;
                    background: rgba(217, 119, 54, 0.2);
                    border: 1px solid #d97736;
                    color: #fba76a;
                    font-size: 0.72rem;
                    font-weight: 700;
                    letter-spacing: 0.08em;
                    padding: 3px 10px;
                    border-radius: 12px;
                    margin-bottom: 8px;
                ">[SYNTHETIC DATA] SIMULATED FLOTATION CIRCUIT</div>
                <h1 style="margin: 0; color: #f8fafc; font-size: 1.85rem; letter-spacing: -0.02em;">
                    RECOVERY OPTIMIZER
                </h1>
                <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 0.95rem;">
                    Closed-Loop Flotation Process Control & Virtual Plant Digital Twin
                </p>
            </div>
            <div style="text-align: right; color: #cbd5e1; font-size: 0.85rem;">
                <span style="display:inline-block; width:8px; height:8px; background:#14b8a6; border-radius:50%; margin-right:6px;"></span>
                <b>Mode:</b> Low-Motion Active
            </div>
        </div>
        """

    # Interactive HTML5 Canvas Animation
    return """
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body, html {
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        #banner-wrap {
            position: relative;
            width: 100%;
            height: 140px;
            border-radius: 12px;
            overflow: hidden;
            background: linear-gradient(180deg, #0b0f19 0%, #131b2e 100%);
            border: 1px solid rgba(217, 119, 54, 0.35);
            box-shadow: 0 8px 30px rgba(0, 0, 0, 0.6);
        }
        canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
        }
        .banner-content {
            position: relative;
            z-index: 2;
            padding: 20px 28px;
            pointer-events: none;
            display: flex;
            justify-content: space-between;
            align-items: center;
            height: calc(100% - 40px);
        }
        .badge-pill {
            display: inline-block;
            background: rgba(217, 119, 54, 0.22);
            border: 1px solid rgba(217, 119, 54, 0.55);
            color: #fba76a;
            font-size: 0.70rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            padding: 3px 10px;
            border-radius: 12px;
            margin-bottom: 6px;
        }
        h1 {
            margin: 0;
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #ffffff;
            text-shadow: 0 2px 10px rgba(0,0,0,0.7);
        }
        h1 span {
            color: #d97736;
        }
        p {
            margin: 4px 0 0 0;
            font-size: 0.90rem;
            color: #cbd5e1;
            text-shadow: 0 1px 4px rgba(0,0,0,0.8);
        }
        .telemetry-status {
            text-align: right;
            font-size: 0.82rem;
            color: #94a3b8;
            background: rgba(11, 15, 25, 0.65);
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.06);
            backdrop-filter: blur(4px);
        }
        .live-dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background-color: #14b8a6;
            box-shadow: 0 0 8px #14b8a6;
            margin-right: 6px;
            animation: pulseDot 2s infinite;
        }
        @keyframes pulseDot {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.4; transform: scale(0.85); }
        }
    </style>
    </head>
    <body>
        <div id="banner-wrap">
            <canvas id="hero-canvas"></canvas>
            <div class="banner-content">
                <div>
                    <div class="badge-pill">[SYNTHETIC DATA] SIMULATED FLOTATION CIRCUIT</div>
                    <h1>RECOVERY <span>OPTIMIZER</span></h1>
                    <p>Closed-Loop Mine-to-Mill Decision Support System</p>
                </div>
                <div class="telemetry-status">
                    <div><span class="live-dot"></span><b>Engine Status:</b> Nominal</div>
                    <div style="font-size: 0.75rem; margin-top: 2px;">Copper Rougher Flotation Circuit</div>
                </div>
            </div>
        </div>

        <script>
            (function() {
                const canvas = document.getElementById("hero-canvas");
                const ctx = canvas.getContext("2d");
                let width, height;

                function resize() {
                    width = canvas.width = canvas.parentElement.clientWidth;
                    height = canvas.height = canvas.parentElement.clientHeight;
                }
                window.addEventListener("resize", resize);
                resize();

                // Particle systems: tumbling rocks & ambient copper dust
                const rocks = [];
                const dust = [];
                const MAX_ROCKS = 28;
                const MAX_DUST = 70;

                for (let i = 0; i < MAX_ROCKS; i++) {
                    rocks.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        radius: 2.0 + Math.random() * 3.5,
                        speedX: 0.8 + Math.random() * 1.6,
                        speedY: 1.2 + Math.random() * 2.2,
                        rotation: Math.random() * Math.PI * 2,
                        rotSpeed: (Math.random() - 0.5) * 0.08,
                        color: Math.random() > 0.4 ? "#a87146" : "#71717a"
                    });
                }

                for (let i = 0; i < MAX_DUST; i++) {
                    dust.push({
                        x: Math.random() * width,
                        y: Math.random() * height,
                        radius: 0.7 + Math.random() * 1.5,
                        speedX: (Math.random() - 0.5) * 0.5,
                        speedY: -0.2 - Math.random() * 0.4,
                        alpha: 0.15 + Math.random() * 0.5,
                        pulse: Math.random() * Math.PI
                    });
                }

                function drawPitSilhouette() {
                    // Layered open-pit bench silhouettes
                    ctx.save();
                    
                    // Far bench (dark navy)
                    ctx.fillStyle = "rgba(13, 21, 38, 0.7)";
                    ctx.beginPath();
                    ctx.moveTo(0, height);
                    ctx.lineTo(0, height * 0.65);
                    ctx.lineTo(width * 0.35, height * 0.82);
                    ctx.lineTo(width * 0.65, height * 0.75);
                    ctx.lineTo(width, height * 0.55);
                    ctx.lineTo(width, height);
                    ctx.closePath();
                    ctx.fill();

                    // Near bench (copper-tinged charcoal)
                    ctx.fillStyle = "rgba(19, 27, 46, 0.85)";
                    ctx.beginPath();
                    ctx.moveTo(0, height);
                    ctx.lineTo(0, height * 0.85);
                    ctx.lineTo(width * 0.25, height * 0.92);
                    ctx.lineTo(width * 0.55, height * 0.88);
                    ctx.lineTo(width * 0.85, height * 0.95);
                    ctx.lineTo(width, height * 0.78);
                    ctx.lineTo(width, height);
                    ctx.closePath();
                    ctx.fill();

                    // Copper gradient glow from pit bottom
                    const glow = ctx.createLinearGradient(0, height, 0, 0);
                    glow.addColorStop(0, "rgba(217, 119, 54, 0.18)");
                    glow.addColorStop(0.6, "rgba(217, 119, 54, 0.04)");
                    glow.addColorStop(1, "rgba(217, 119, 54, 0)");
                    ctx.fillStyle = glow;
                    ctx.fillRect(0, 0, width, height);

                    ctx.restore();
                }

                function animate() {
                    ctx.clearRect(0, 0, width, height);
                    drawPitSilhouette();

                    // Animate dust particles
                    ctx.save();
                    for (let d of dust) {
                        d.y += d.speedY;
                        d.x += d.speedX;
                        d.pulse += 0.03;
                        const dynamicAlpha = Math.max(0.1, d.alpha + Math.sin(d.pulse) * 0.2);

                        if (d.y < 0) {
                            d.y = height + 5;
                            d.x = Math.random() * width;
                        }

                        ctx.fillStyle = `rgba(217, 119, 54, ${dynamicAlpha})`;
                        ctx.beginPath();
                        ctx.arc(d.x, d.y, d.radius, 0, Math.PI * 2);
                        ctx.fill();
                    }
                    ctx.restore();

                    // Animate tumbling rocks
                    ctx.save();
                    for (let r of rocks) {
                        r.x += r.speedX;
                        r.y += r.speedY;
                        r.rotation += r.rotSpeed;

                        if (r.y > height + 10 || r.x > width + 10) {
                            r.y = -10;
                            r.x = Math.random() * (width * 0.8);
                        }

                        ctx.save();
                        ctx.translate(r.x, r.y);
                        ctx.rotate(r.rotation);
                        ctx.fillStyle = r.color;
                        ctx.beginPath();
                        // Irregular rocky polygon
                        ctx.moveTo(-r.radius, -r.radius * 0.7);
                        ctx.lineTo(r.radius * 0.8, -r.radius);
                        ctx.lineTo(r.radius, r.radius * 0.6);
                        ctx.lineTo(-r.radius * 0.5, r.radius);
                        ctx.closePath();
                        ctx.fill();
                        ctx.restore();
                    }
                    ctx.restore();

                    requestAnimationFrame(animate);
                }

                animate();
            })();
        </script>
    </body>
    </html>
    """


def render_ore_to_product_scene(reduced_animations: bool = False) -> str:
    """
    Renders the 'Ore to Product' animated scene (SVG + CSS).
    Features:
    - Conveyor belt carrying feed rocks across the screen
    - Primary gyratory crusher with mechanical shaking vibration
    - Rougher flotation cell with rising air bubbles that selectively attach to
      copper-colored particles and float them over the lip into a 'Concentrate' bin,
      while unfloated grey gangue rocks sink into a 'Tailings' bin.
    - Plain-language labels for every component.
    """
    shake_anim = "animation: crusherShake 0.14s infinite ease-in-out;" if not reduced_animations else ""
    conveyor_anim = "animation: beltMove 1.8s linear infinite;" if not reduced_animations else ""
    bubble_anim_1 = "animation: bubbleFloat 2.2s infinite ease-in;" if not reduced_animations else ""
    bubble_anim_2 = "animation: bubbleFloat 2.6s 0.7s infinite ease-in;" if not reduced_animations else ""
    bubble_anim_3 = "animation: bubbleFloat 1.9s 1.2s infinite ease-in;" if not reduced_animations else ""
    cu_float_anim = "animation: floatToConc 2.5s infinite ease-out;" if not reduced_animations else ""
    tailings_sink_anim = "animation: sinkToTail 2.8s infinite ease-in;" if not reduced_animations else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #f1f5f9;
        }}
        .scene-container {{
            background: linear-gradient(135deg, rgba(19, 27, 46, 0.85) 0%, rgba(13, 19, 34, 0.95) 100%);
            border: 1px solid rgba(217, 119, 54, 0.28);
            border-radius: 12px;
            padding: 18px 24px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.45);
        }}
        .scene-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            padding-bottom: 8px;
        }}
        .scene-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #f8fafc;
        }}
        .scene-title span {{
            color: #d97736;
        }}
        .legend-tag {{
            font-size: 0.78rem;
            color: #94a3b8;
            display: flex;
            gap: 14px;
        }}
        .dot-cu {{ display: inline-block; width: 8px; height: 8px; background: #d97736; border-radius: 50%; margin-right: 4px; }}
        .dot-gangue {{ display: inline-block; width: 8px; height: 8px; background: #64748b; border-radius: 50%; margin-right: 4px; }}
        .dot-air {{ display: inline-block; width: 8px; height: 8px; background: #38bdf8; border-radius: 50%; margin-right: 4px; }}

        /* Animations */
        @keyframes crusherShake {{
            0% {{ transform: translate(0, 0) rotate(0deg); }}
            25% {{ transform: translate(-1.5px, 1px) rotate(-0.5deg); }}
            50% {{ transform: translate(1px, -1.5px) rotate(0.5deg); }}
            75% {{ transform: translate(-1px, -1px) rotate(0deg); }}
            100% {{ transform: translate(0, 0) rotate(0deg); }}
        }}
        @keyframes beltMove {{
            0% {{ stroke-dashoffset: 0; }}
            100% {{ stroke-dashoffset: 24; }}
        }}
        @keyframes bubbleFloat {{
            0% {{ transform: translateY(75px) scale(0.6); opacity: 0.1; }}
            30% {{ opacity: 0.9; }}
            80% {{ transform: translateY(12px) scale(1.1); opacity: 0.8; }}
            100% {{ transform: translateY(0px) scale(1.2); opacity: 0; }}
        }}
        @keyframes floatToConc {{
            0% {{ transform: translate(0, 60px) scale(0.7); opacity: 0.2; }}
            40% {{ transform: translate(12px, 15px) scale(1.0); opacity: 0.9; }}
            80% {{ transform: translate(45px, -6px) scale(1.1); opacity: 0.95; }}
            100% {{ transform: translate(75px, 22px) scale(0.9); opacity: 0; }}
        }}
        @keyframes sinkToTail {{
            0% {{ transform: translate(0, 30px); opacity: 0.8; }}
            50% {{ transform: translate(-8px, 60px); opacity: 0.9; }}
            100% {{ transform: translate(45px, 85px); opacity: 0; }}
        }}
    </style>
    </head>
    <body>
        <div class="scene-container">
            <div class="scene-header">
                <div class="scene-title">ORE TO PRODUCT: <span>Physical Beneficiation & Flotation Separation</span></div>
                <div class="legend-tag">
                    <span><span class="dot-cu"></span>Copper Chalcopyrite</span>
                    <span><span class="dot-gangue"></span>Waste Gangue Rock</span>
                    <span><span class="dot-air"></span>Hydrophobic Air Bubbles</span>
                </div>
            </div>

            <svg viewBox="0 0 950 210" width="100%" height="210" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <!-- Linear Gradients -->
                    <linearGradient id="crusherGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="#334155"/>
                        <stop offset="100%" stop-color="#1e293b"/>
                    </linearGradient>
                    <linearGradient id="flotationPulp" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#0284c7" stop-opacity="0.35"/>
                        <stop offset="100%" stop-color="#0369a1" stop-opacity="0.75"/>
                    </linearGradient>
                    <linearGradient id="concGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#d97736"/>
                        <stop offset="100%" stop-color="#9a3412"/>
                    </linearGradient>
                    <linearGradient id="tailGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stop-color="#475569"/>
                        <stop offset="100%" stop-color="#1e293b"/>
                    </linearGradient>
                </defs>

                <!-- SECTION 1: RUN-OF-MINE ORE & CONVEYOR -->
                <g transform="translate(15, 40)">
                    <rect x="0" y="55" width="190" height="12" rx="4" fill="#1e293b" stroke="#475569" stroke-width="1.5"/>
                    <line x1="5" y1="61" x2="185" y2="61" stroke="#d97736" stroke-width="3" stroke-dasharray="8 4" style="{conveyor_anim}"/>
                    <!-- Roller Wheels -->
                    <circle cx="20" cy="74" r="7" fill="#334155" stroke="#64748b"/>
                    <circle cx="95" cy="74" r="7" fill="#334155" stroke="#64748b"/>
                    <circle cx="170" cy="74" r="7" fill="#334155" stroke="#64748b"/>

                    <!-- Rocks on belt -->
                    <polygon points="30,52 38,40 48,46 44,54" fill="#78716c"/>
                    <polygon points="70,53 79,43 89,48 83,55" fill="#a8a29e"/>
                    <polygon points="82,51 90,41 98,47 93,54" fill="#d97736"/>
                    <polygon points="130,53 140,38 152,44 146,55" fill="#78716c"/>
                    <polygon points="144,52 153,42 161,48 156,54" fill="#b45309"/>

                    <text x="95" y="105" text-anchor="middle" fill="#94a3b8" font-size="11" font-weight="600">Feed Conveyor (ROM Ore)</text>
                    <text x="95" y="120" text-anchor="middle" fill="#64748b" font-size="9.5">1,850 t/h • 0.75% Cu</text>
                </g>

                <!-- SECTION 2: PRIMARY GYRATORY CRUSHER -->
                <g transform="translate(225, 20)">
                    <g style="{shake_anim}">
                        <!-- Crusher Frame Housing -->
                        <polygon points="35,20 105,20 88,95 52,95" fill="url(#crusherGrad)" stroke="#d97736" stroke-width="1.5"/>
                        <rect x="30" y="10" width="80" height="12" rx="3" fill="#475569" stroke="#94a3b8" stroke-width="1"/>
                        <!-- Mantle Core -->
                        <polygon points="62,30 78,30 73,85 67,85" fill="#f97316" opacity="0.85"/>
                    </g>
                    <!-- Base Stand -->
                    <rect x="42" y="96" width="56" height="28" fill="#0f172a" stroke="#334155" stroke-width="1.5"/>
                    <text x="70" y="145" text-anchor="middle" fill="#f8fafc" font-size="11.5" font-weight="700">Primary Crusher</text>
                    <text x="70" y="160" text-anchor="middle" fill="#14b8a6" font-size="9.5">Size Reduction to P80</text>
                </g>

                <!-- CONVEYOR 2 (CRUSHER TO FLOTATION) -->
                <g transform="translate(345, 50)">
                    <line x1="0" y1="52" x2="70" y2="52" stroke="#64748b" stroke-width="4" stroke-dasharray="6 3" style="{conveyor_anim}"/>
                    <polygon points="18,48 24,42 32,46 29,51" fill="#d97736"/>
                    <polygon points="38,49 43,44 50,47 47,51" fill="#78716c"/>
                </g>

                <!-- SECTION 3: ROUGHER FLOTATION TANK -->
                <g transform="translate(435, 15)">
                    <!-- Tank Outer Shell -->
                    <rect x="0" y="20" width="170" height="120" rx="8" fill="url(#flotationPulp)" stroke="#38bdf8" stroke-width="2"/>
                    <!-- Impeller Shaft & Rotor -->
                    <rect x="80" y="0" width="10" height="100" fill="#64748b" stroke="#94a3b8"/>
                    <polygon points="60,100 110,100 100,115 70,115" fill="#0284c7" stroke="#38bdf8" stroke-width="1.5"/>

                    <!-- Froth Layer on Top -->
                    <rect x="2" y="22" width="166" height="18" fill="rgba(217, 119, 54, 0.45)" stroke="rgba(251, 167, 106, 0.6)"/>
                    <circle cx="20" cy="30" r="3" fill="#fba76a" opacity="0.8"/>
                    <circle cx="35" cy="28" r="4" fill="#fba76a" opacity="0.8"/>
                    <circle cx="55" cy="31" r="3.5" fill="#fba76a" opacity="0.8"/>
                    <circle cx="85" cy="29" r="4.5" fill="#fba76a" opacity="0.8"/>
                    <circle cx="120" cy="30" r="3.5" fill="#fba76a" opacity="0.8"/>
                    <circle cx="145" cy="28" r="4" fill="#fba76a" opacity="0.8"/>

                    <!-- Rising Bubbles (Animated) -->
                    <g transform="translate(45, 35)">
                        <circle cx="0" cy="0" r="4" fill="#7dd3fc" opacity="0.7" style="{bubble_anim_1}"/>
                        <circle cx="35" cy="0" r="5" fill="#7dd3fc" opacity="0.8" style="{bubble_anim_2}"/>
                        <circle cx="65" cy="0" r="3.5" fill="#7dd3fc" opacity="0.6" style="{bubble_anim_3}"/>
                    </g>

                    <!-- Copper particles floating to froth -->
                    <g transform="translate(75, 45)">
                        <circle cx="0" cy="0" r="3.5" fill="#f97316" style="{cu_float_anim}"/>
                        <circle cx="10" cy="5" r="4.0" fill="#d97736" style="{cu_float_anim}"/>
                    </g>

                    <!-- Gangue particles sinking to bottom -->
                    <g transform="translate(50, 40)">
                        <circle cx="0" cy="0" r="4.5" fill="#64748b" style="{tailings_sink_anim}"/>
                        <circle cx="15" cy="-5" r="4.0" fill="#475569" style="{tailings_sink_anim}"/>
                    </g>

                    <text x="85" y="160" text-anchor="middle" fill="#f8fafc" font-size="12" font-weight="700">Rougher Flotation Cell</text>
                    <text x="85" y="175" text-anchor="middle" fill="#38bdf8" font-size="9.5">Air + Collector (PAX) + pH 11.2</text>
                </g>

                <!-- SECTION 4: LAUNDER & DISCHARGE ARROWS -->
                <!-- Froth Overflow Launder to Concentrate -->
                <path d="M 605 40 Q 640 40 660 65" fill="none" stroke="#d97736" stroke-width="3.5" stroke-dasharray="5 3" style="{conveyor_anim}"/>
                <!-- Tailings Underflow -->
                <path d="M 605 130 Q 640 130 660 145" fill="none" stroke="#64748b" stroke-width="3.5" stroke-dasharray="5 3" style="{conveyor_anim}"/>

                <!-- SECTION 5: FINAL PRODUCTS (CONCENTRATE & TAILINGS) -->
                <!-- Concentrate Bin (Top Right) -->
                <g transform="translate(670, 30)">
                    <rect x="0" y="0" width="130" height="58" rx="6" fill="url(#concGrad)" stroke="#fba76a" stroke-width="1.5"/>
                    <text x="65" y="24" text-anchor="middle" fill="#ffffff" font-size="11.5" font-weight="800">CONCENTRATE</text>
                    <text x="65" y="40" text-anchor="middle" fill="#fef08a" font-size="9.5" font-weight="700">28.0% Cu • High Value</text>
                    <text x="65" y="52" text-anchor="middle" fill="#ffedd5" font-size="8.5">+11.1 t/d Extra Metal</text>
                </g>

                <!-- Tailings Disposal (Bottom Right) -->
                <g transform="translate(670, 115)">
                    <rect x="0" y="0" width="130" height="52" rx="6" fill="url(#tailGrad)" stroke="#64748b" stroke-width="1.5"/>
                    <text x="65" y="24" text-anchor="middle" fill="#e2e8f0" font-size="11.5" font-weight="700">TAILINGS</text>
                    <text x="65" y="40" text-anchor="middle" fill="#94a3b8" font-size="9">0.076% Cu • Gangue Waste</text>
                </g>

                <!-- Recovery Callout Banner -->
                <g transform="translate(820, 75)">
                    <rect x="0" y="0" width="115" height="55" rx="8" fill="rgba(20, 184, 166, 0.15)" stroke="#14b8a6" stroke-width="1.5"/>
                    <text x="57" y="22" text-anchor="middle" fill="#2dd4bf" font-size="11" font-weight="700">RECOVERY</text>
                    <text x="57" y="44" text-anchor="middle" fill="#ffffff" font-size="16" font-weight="900">90.1%</text>
                </g>
            </svg>
        </div>
    </body>
    </html>
    """


def render_closed_loop_diagram(reduced_animations: bool = False) -> str:
    """
    Renders the 5-Stage Closed Decision Loop interactive diagram:
      SPC -> DOE -> Simulation -> Blending -> Post-Trial SPC Re-Verification.
    Features:
    - Glowing glass nodes with step numbers
    - Flowing dashed arrows between stages
    - Interactive hover cards providing a one-line plain language explanation for each step.
    """
    arrow_anim = "animation: arrowFlow 1.6s linear infinite;" if not reduced_animations else ""

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="utf-8">
    <style>
        body, html {{
            margin: 0;
            padding: 0;
            overflow: hidden;
            background: transparent;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #f1f5f9;
        }}
        .loop-card {{
            background: rgba(19, 27, 46, 0.75);
            border: 1px solid rgba(217, 119, 54, 0.3);
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
        }}
        .loop-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .loop-title {{
            font-size: 1.05rem;
            font-weight: 700;
            color: #f8fafc;
        }}
        .loop-title span {{
            color: #d97736;
        }}
        .node-group {{
            cursor: pointer;
            transition: all 0.25s ease;
        }}
        .node-group:hover rect.node-box {{
            stroke: #d97736;
            stroke-width: 2.5;
            filter: drop-shadow(0 0 8px rgba(217, 119, 54, 0.6));
        }}
        .node-group:hover text.node-title {{
            fill: #fba76a;
        }}
        @keyframes arrowFlow {{
            0% {{ stroke-dashoffset: 24; }}
            100% {{ stroke-dashoffset: 0; }}
        }}
        .arrow-line {{
            stroke: #d97736;
            stroke-width: 2.5;
            stroke-dasharray: 6 3;
            fill: none;
            {arrow_anim}
        }}
        .return-line {{
            stroke: #14b8a6;
            stroke-width: 2.5;
            stroke-dasharray: 6 3;
            fill: none;
            {arrow_anim}
        }}
    </style>
    </head>
    <body>
        <div class="loop-card">
            <div class="loop-header">
                <div class="loop-title">THE CLOSED DECISION LOOP: <span>Virtual Optimization to Plant Execution</span></div>
                <div style="font-size:0.80rem; color:#94a3b8;">Hover any stage to reveal operational function</div>
            </div>

            <svg viewBox="0 0 960 160" width="100%" height="160" xmlns="http://www.w3.org/2000/svg">
                <!-- ARROWS CONNECTING THE STAGES -->
                <!-- Node 1 -> Node 2 -->
                <path d="M 180 50 L 225 50" class="arrow-line" marker-end="url(#arrowhead)"/>
                <!-- Node 2 -> Node 3 -->
                <path d="M 405 50 L 450 50" class="arrow-line" marker-end="url(#arrowhead)"/>
                <!-- Node 3 -> Node 4 -->
                <path d="M 630 50 L 675 50" class="arrow-line" marker-end="url(#arrowhead)"/>
                <!-- Node 4 -> Node 5 (Down & Left Return Loop) -->
                <path d="M 765 85 L 765 125 L 100 125 L 100 85" class="return-line" marker-end="url(#teal-arrowhead)"/>

                <defs>
                    <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#d97736"/>
                    </marker>
                    <marker id="teal-arrowhead" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#14b8a6"/>
                    </marker>
                </defs>

                <!-- NODE 1: SPC DETECTION -->
                <g class="node-group" transform="translate(20, 15)">
                    <rect class="node-box" x="0" y="0" width="160" height="70" rx="8" fill="#131b2e" stroke="#ef4444" stroke-width="1.8"/>
                    <circle cx="20" cy="20" r="10" fill="rgba(239, 68, 68, 0.25)" stroke="#ef4444"/>
                    <text x="20" y="24" text-anchor="middle" fill="#fca5a5" font-size="10" font-weight="800">1</text>
                    <text class="node-title" x="38" y="24" fill="#f1f5f9" font-size="12" font-weight="700">SPC Drift Detect</text>
                    <text x="12" y="44" fill="#94a3b8" font-size="9.5">EWMA & Western Electric</text>
                    <text x="12" y="58" fill="#ef4444" font-size="9">Cpk drops 0.57 → -0.24</text>
                    <title>Stage 1: Statistical Process Control monitors shift recovery and flags cyclone apex wear drift and lime scaling days before total failure.</title>
                </g>

                <!-- NODE 2: DOE INVESTIGATION -->
                <g class="node-group" transform="translate(245, 15)">
                    <rect class="node-box" x="0" y="0" width="160" height="70" rx="8" fill="#131b2e" stroke="#d97736" stroke-width="1.8"/>
                    <circle cx="20" cy="20" r="10" fill="rgba(217, 119, 54, 0.25)" stroke="#d97736"/>
                    <text x="20" y="24" text-anchor="middle" fill="#fba76a" font-size="10" font-weight="800">2</text>
                    <text class="node-title" x="38" y="24" fill="#f1f5f9" font-size="12" font-weight="700">DOE Factor Study</text>
                    <text x="12" y="44" fill="#94a3b8" font-size="9.5">2^(4-1) & CCD Surface</text>
                    <text x="12" y="58" fill="#d97736" font-size="9">Finds pH x Dose Synergy</text>
                    <title>Stage 2: Design of Experiments screens 4 factors and maps 2nd-order response surface, discovering optimal grind size (75 um) and pH (11.2).</title>
                </g>

                <!-- NODE 3: FEED BLENDING OPTIMIZATION -->
                <g class="node-group" transform="translate(470, 15)">
                    <rect class="node-box" x="0" y="0" width="160" height="70" rx="8" fill="#131b2e" stroke="#38bdf8" stroke-width="1.8"/>
                    <circle cx="20" cy="20" r="10" fill="rgba(56, 189, 248, 0.25)" stroke="#38bdf8"/>
                    <text x="20" y="24" text-anchor="middle" fill="#7dd3fc" font-size="10" font-weight="800">3</text>
                    <text class="node-title" x="38" y="24" fill="#f1f5f9" font-size="12" font-weight="700">Feed Blending LP</text>
                    <text x="12" y="44" fill="#94a3b8" font-size="9.5">PuLP / HiGHS Solver</text>
                    <text x="12" y="58" fill="#38bdf8" font-size="9">Hits 0.75% Cu & 14.5 BWi</text>
                    <title>Stage 3: Goal Programming Linear Program blends stockpile ores to guarantee consistent mill feed hardness and head grade, eliminating disturbances.</title>
                </g>

                <!-- NODE 4: SIMPY VIRTUAL TWIN -->
                <g class="node-group" transform="translate(695, 15)">
                    <rect class="node-box" x="0" y="0" width="160" height="70" rx="8" fill="#131b2e" stroke="#a855f7" stroke-width="1.8"/>
                    <circle cx="20" cy="20" r="10" fill="rgba(168, 85, 247, 0.25)" stroke="#a855f7"/>
                    <text x="20" y="24" text-anchor="middle" fill="#d8b4fe" font-size="10" font-weight="800">4</text>
                    <text class="node-title" x="38" y="24" fill="#f1f5f9" font-size="12" font-weight="700">SimPy Virtual Twin</text>
                    <text x="12" y="44" fill="#94a3b8" font-size="9.5">15 Reps w/ 95% CIs</text>
                    <text x="12" y="58" fill="#a855f7" font-size="9">Validates Stockpile Buffer</text>
                    <title>Stage 4: Discrete-event simulation tests haul fleet dynamics and proved that the 18,000t buffer absorbs 4-hour crusher downtime before plant trials.</title>
                </g>

                <!-- NODE 5 / CONFIRMATION: SPC RE-VERIFICATION -->
                <text x="480" y="142" text-anchor="middle" fill="#14b8a6" font-size="10.5" font-weight="700">
                    ↺ Stage 5: SPC Re-Verification Confirms Recovery Restoration to 90.1% (Cpk Restored to > 1.20)
                </text>
            </svg>
        </div>
    </body>
    </html>
    """

