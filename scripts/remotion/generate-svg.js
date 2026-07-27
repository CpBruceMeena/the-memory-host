/**
 * Generate a standalone SVG file of the AWS Architecture Diagram.
 * This renders the React component server-side and extracts the SVG markup.
 */
const path = require("path");
const fs = require("fs");

// Generate SVG markup programmatically based on the ArchitectureDiagram.tsx component design

const W = 1920;
const H = 1080;

// Colors
const C = {
  bg: "#0B1426",
  grid: "#1A2744",
  text: "#E2E8F0",
  muted: "#94A3B8",
  accent: "#38BDF8",
  compute: "#FF9900",
  computeBg: "#FF990015",
  database: "#3B82F6",
  databaseBg: "#3B82F615",
  network: "#8B5CF6",
  networkBg: "#8B5CF615",
  storage: "#10B981",
  storageBg: "#10B98115",
  security: "#EF4444",
  securityBg: "#EF444415",
  monitoring: "#F59E0B",
  monitoringBg: "#F59E0B15",
  integration: "#EC4899",
  integrationBg: "#EC489915",
  flowLine: "#38BDF860",
  flowArrow: "#38BDF8",
  layer1: "#0F1A36",
  layer2: "#141F3D",
  layer3: "#192844",
  layerBg: "#38BDF808",
  boxBg: "#1E293B",
  boxBorder: "#334155",
  boxShadow: "#00000040",
  userBox: "#2D1B69",
  userBorder: "#8B5CF6",
};

const FONT = "'Inter','SF Pro Display',-apple-system,sans-serif";
const FONT_MONO = "'JetBrains Mono','SF Mono','Fira Code',monospace";

/** Helper: service box */
function box(x, y, w, h, label, sublabel, color, bg, hl) {
  const parts = [
    hl ? `<rect x="${x-2}" y="${y-2}" width="${w+4}" height="${h+4}" rx="10" fill="${color}10" stroke="${color}30" stroke-width="1"/>` : "",
    `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" fill="${bg||C.boxBg}" stroke="${color}" stroke-width="${hl?2:1}" stroke-opacity="${hl?0.9:0.6}" filter="url(#shadow)"/>`,
    `<rect x="${x+1}" y="${y+1}" width="${w-2}" height="3" rx="2" fill="${color}" fill-opacity="0.7"/>`,
    `<text x="${x+w/2}" y="${y+(sublabel?26:34)}" fill="${C.text}" font-size="${sublabel?13:14}" font-family="${FONT}" font-weight="600" text-anchor="middle" dominant-baseline="central">${label}</text>`,
  ];
  if (sublabel) {
    parts.push(`<text x="${x+w/2}" y="${y+42}" fill="${C.muted}" font-size="10" font-family="${FONT_MONO}" font-weight="400" text-anchor="middle" dominant-baseline="central">${sublabel}</text>`);
  }
  return parts.join("\n");
}

/** Helper: arrow */
function arrow(x1, y1, x2, y2, label, color, dashed, glow) {
  const c = color || C.flowLine;
  const dx = x2 - x1, dy = y2 - y1;
  const angle = Math.atan2(dy, dx) * 180 / Math.PI;
  const ax = x2, ay = y2;
  const dash = dashed ? ' stroke-dasharray="6,4"' : "";
  const parts = [
    glow ? `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="6" stroke-opacity="0.15"${dash}/>` : "",
    `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="2" stroke-opacity="0.8"${dash}/>`,
    `<polygon points="${ax-8},${ay-5} ${ax},${ay} ${ax-8},${ay+5}" fill="${c}" fill-opacity="0.8" transform="rotate(${angle},${ax},${ay})"/>`,
  ];
  if (label) {
    parts.push(`<text x="${(x1+x2)/2}" y="${(y1+y2)/2-10}" fill="${C.muted}" font-size="9" font-family="${FONT}" font-weight="500" text-anchor="middle" dominant-baseline="central">${label}</text>`);
  }
  return parts.join("\n");
}

/** Helper: layer label */
function layerLabel(x, y, label, sublabel) {
  return `
    <text x="${x}" y="${y}" fill="${C.text}" font-size="16" font-family="${FONT}" font-weight="700" text-anchor="start" dominant-baseline="central">${label}</text>
    <text x="${x}" y="${y+22}" fill="${C.muted}" font-size="11" font-family="${FONT}" font-weight="400" text-anchor="start" dominant-baseline="central">${sublabel}</text>
  `;
}

/** Helper: metric card */
function metricCard(x, y, label, value, color) {
  return `
    <rect x="${x}" y="${y}" width="130" height="48" rx="6" fill="${C.boxBg}" stroke="${color}40" stroke-width="1"/>
    <text x="${x+65}" y="${y+16}" fill="${color}" font-size="15" font-family="${FONT_MONO}" font-weight="700" text-anchor="middle" dominant-baseline="central">${value}</text>
    <text x="${x+65}" y="${y+33}" fill="${C.muted}" font-size="9" font-family="${FONT}" font-weight="500" text-anchor="middle" dominant-baseline="central">${label}</text>
  `;
}

/** Helper: legend item */
function legendItem(x, y, color, label) {
  return `
    <rect x="${x}" y="${y-5}" width="12" height="12" rx="2" fill="${color}4D" stroke="${color}" stroke-width="1"/>
    <text x="${x+18}" y="${y+1}" fill="${C.text}" font-size="10" font-family="${FONT}" font-weight="500" text-anchor="start" dominant-baseline="central">${label}</text>
  `;
}

// ─── BUILD SVG ───────────────────────────────────────────────────────────────

const svgContent = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" style="background:${C.bg}">
  <defs>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
      <path d="M 40 0 L 0 0 0 40" fill="none" stroke="${C.grid}" stroke-width="0.5" stroke-opacity="0.3"/>
    </pattern>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="${C.boxShadow}" flood-opacity="0.5"/>
    </filter>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="userGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${C.userBox}"/>
      <stop offset="100%" stop-color="#1A1050"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="${W}" height="${H}" fill="url(#grid)"/>

  <!-- ===== TITLE & METRICS ===== -->
  <g>
    <rect x="30" y="20" width="44" height="44" rx="12" fill="${C.accent}26" stroke="${C.accent}" stroke-width="1"/>
    <text x="52" y="42" fill="${C.accent}" font-size="22" font-family="${FONT}" font-weight="800" text-anchor="middle" dominant-baseline="central">MH</text>
    <text x="90" y="35" fill="${C.text}" font-size="20" font-family="${FONT}" font-weight="700">The Memory Host — AWS Architecture</text>
    <text x="90" y="55" fill="${C.muted}" font-size="12" font-family="${FONT}" font-weight="400">Real-time voice memory game · 1M Total Users · 100K Daily Active Users · 10K Peak Concurrent</text>
    ${metricCard(1300, 18, "Avg Latency (STT→TTS)", "<1.2s", C.accent)}
    ${metricCard(1440, 18, "Peak Sessions", "10K", C.compute)}
    ${metricCard(1580, 18, "Daily Game Rounds", "500K", C.integration)}
    ${metricCard(1720, 18, "Data Ingest / Day", "~150GB", C.database)}
  </g>

  <!-- Legend -->
  <g>
    ${legendItem(30, 1050, C.compute, "Compute / Container")}
    ${legendItem(190, 1050, C.network, "Networking / CDN")}
    ${legendItem(360, 1050, C.database, "Database / Storage")}
    ${legendItem(530, 1050, C.security, "Security / WAF")}
    ${legendItem(700, 1050, C.monitoring, "Monitoring / Observability")}
    ${legendItem(910, 1050, C.integration, "Integration / CI-CD")}
    ${legendItem(1100, 1050, C.storage, "Object Storage")}
  </g>

  <!-- Region badge -->
  <rect x="1720" y="1030" width="100" height="22" rx="11" fill="${C.boxBg}" stroke="${C.boxBorder}" stroke-width="1"/>
  <text x="1770" y="1041" fill="${C.accent}" font-size="10" font-family="${FONT_MONO}" font-weight="600" text-anchor="middle" dominant-baseline="central">eu-west-1</text>

  <!-- ================================================================ -->
  <!-- LAYER 1: User & Edge -->
  <!-- ================================================================ -->
  <rect x="20" y="80" width="1880" height="120" rx="12" fill="${C.layer1}" fill-opacity="0.5" stroke="${C.layerBg}" stroke-width="1"/>
  ${layerLabel(36, 98, "👤 User & Edge", "DNS · CDN · DDoS Protection")}

  <!-- User browser -->
  <rect x="60" y="125" width="150" height="58" rx="10" fill="url(#userGrad)" stroke="${C.userBorder}" stroke-width="1.5" filter="url(#shadow)"/>
  <text x="135" y="152" fill="${C.text}" font-size="22" font-family="${FONT}" text-anchor="middle" dominant-baseline="central">🌐</text>
  <text x="135" y="171" fill="${C.text}" font-size="12" font-family="${FONT}" font-weight="600" text-anchor="middle" dominant-baseline="central">User Browser</text>

  ${box(350, 120, 150, 58, "Route 53", "DNS · Latency-based", C.network, C.networkBg)}
  ${box(560, 120, 190, 58, "CloudFront + WAF", "CDN · SSL · Rate Limit", C.security, C.securityBg)}
  ${arrow(210, 155, 345, 155, "HTTPS", C.network)}
  ${arrow(500, 155, 555, 155)}

  <!-- ================================================================ -->
  <!-- LAYER 2: Application Layer -->
  <!-- ================================================================ -->
  <rect x="20" y="230" width="1880" height="290" rx="12" fill="${C.layer2}" fill-opacity="0.5" stroke="${C.layerBg}" stroke-width="1"/>
  ${layerLabel(36, 248, "⚙️ Application Layer", "ECS Fargate · Auto Scaling · Load Balancers")}

  <!-- ECS Cluster label -->
  <rect x="310" y="265" width="910" height="20" rx="4" fill="${C.compute}" fill-opacity="0.08" stroke="${C.compute}" stroke-width="0.5"/>
  <text x="765" y="278" fill="${C.compute}" font-size="10" font-family="${FONT_MONO}" font-weight="600" text-anchor="middle" dominant-baseline="central">Amazon ECS Cluster — Fargate (ARM64)</text>

  ${box(60, 280, 180, 60, "ALB", "HTTPS Ingress", C.network, C.networkBg, true)}
  ${box(60, 365, 180, 60, "NLB", "WebSocket Passthrough", C.network, C.networkBg)}

  ${box(310, 275, 180, 75, "Next.js Frontend", "Port 3000 · 8 tasks", C.compute, C.computeBg)}
  <text x="400" y="372" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">12x Fargate tasks · min 6</text>

  ${box(530, 275, 180, 75, "REST API", "Port 8000 · FastAPI", C.compute, C.computeBg)}
  <text x="620" y="372" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">8x Fargate tasks · min 4</text>

  ${box(750, 355, 180, 65, "Signaling Server", "Port 3001 · WebSocket", C.compute, C.computeBg)}
  <text x="840" y="438" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">6x Fargate tasks · sticky-ws</text>

  ${box(1000, 275, 220, 95, "🎙️ Game Engine", "Pipecat Bots · Port 3002", C.integration, C.integrationBg, true)}
  <text x="1110" y="358" fill="${C.integration}" font-size="11" font-family="${FONT}" text-anchor="middle" dominant-baseline="central">Each session = 1 Pipecat Pipeline</text>
  <text x="1110" y="392" fill="${C.compute}" font-size="10" font-family="${FONT_MONO}" font-weight="600" text-anchor="middle">&gt;10K concurrent bot pipelines</text>

  ${box(1280, 355, 180, 65, "Coturn TURN", "WebRTC NAT Traversal", C.network, C.networkBg)}
  <text x="1370" y="438" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">EC2 c6i.large × 4 (ASG)</text>

  <!-- Data flow: CloudFront → ALB -->
  ${arrow(750, 150, 750, 275, "HTTPS", C.network)}
  ${arrow(240, 310, 305, 310)}
  ${arrow(240, 315, 525, 315, "/api/* → BFF", C.compute)}
  ${arrow(490, 310, 525, 310, "", C.compute)}
  ${arrow(710, 315, 995, 315, "POST /start-session", C.integration, true)}
  ${arrow(240, 395, 745, 395, "WebSocket", C.network)}
  ${arrow(930, 390, 995, 370, "ws:3001", C.flowArrow)}
  ${arrow(1220, 365, 1275, 390, "TURN relay", C.network, true)}
  ${arrow(135, 183, 1110, 270, "WebRTC (SRTP) Audio", C.integration, false, true)}
  ${arrow(135, 188, 840, 350, "Signaling WS", C.network, true)}

  <!-- ================================================================ -->
  <!-- LAYER 3: Data & Persistence -->
  <!-- ================================================================ -->
  <rect x="20" y="550" width="1880" height="230" rx="12" fill="${C.layer3}" fill-opacity="0.5" stroke="${C.layerBg}" stroke-width="1"/>
  ${layerLabel(36, 568, "🗄️ Data & Persistence", "Multi-AZ · Read Replicas · Caching")}

  ${box(60, 595, 220, 80, "Aurora PostgreSQL", "Primary (writer)", C.database, C.databaseBg, true)}
  <text x="170" y="695" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">db.r7g.large · Multi-AZ</text>

  ${box(320, 595, 200, 80, "Aurora Read Replica", "5 x db.r7g.large", C.database, C.databaseBg)}
  <text x="420" y="695" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">Auto-scaling replicas</text>

  ${box(580, 595, 200, 80, "ElastiCache Redis", "Session + Leaderboard", C.database, C.databaseBg)}
  <text x="680" y="695" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle">cache.r7g.large · cluster</text>

  ${box(840, 595, 200, 80, "S3 Static Assets", "Logs · Build Artifacts", C.storage, C.storageBg)}

  <!-- Deepgram (External) -->
  <rect x="1100" y="595" width="220" height="80" rx="8" fill="${C.integrationBg}" stroke="${C.integration}" stroke-width="1" stroke-dasharray="6,3" filter="url(#shadow)"/>
  <text x="1210" y="622" fill="${C.integration}" font-size="14" font-family="${FONT}" font-weight="600" text-anchor="middle" dominant-baseline="central">☁️ Deepgram Cloud</text>
  <text x="1210" y="642" fill="${C.text}" font-size="11" font-family="${FONT}" text-anchor="middle" dominant-baseline="central">Nova-2 STT · Aura-2 TTS</text>
  <text x="1210" y="660" fill="${C.muted}" font-size="9" font-family="${FONT}" text-anchor="middle" dominant-baseline="central">~100K API calls / peak hour</text>

  <!-- Data arrows to persistence layer -->
  ${arrow(490, 355, 490, 590, "reads polls", C.database)}
  ${arrow(1110, 375, 1110, 590, "writes scores", C.database)}
  ${arrow(620, 355, 420, 590, "", C.database)}
  ${arrow(1110, 370, 170, 590, "", C.database)}
  ${arrow(680, 355, 680, 590, "cache", C.database, true)}
  ${arrow(1220, 375, 1220, 590, "STT/TTS API", C.integration, true)}

  <!-- ================================================================ -->
  <!-- LAYER 4: Observability & CI/CD -->
  <!-- ================================================================ -->
  <rect x="20" y="810" width="1880" height="120" rx="12" fill="${C.layer1}" fill-opacity="0.3" stroke="${C.layerBg}" stroke-width="1"/>
  ${layerLabel(36, 830, "📊 Observability & CI/CD", "Monitoring · Logging · Deployment")}

  ${box(60, 850, 160, 60, "CloudWatch", "Logs · Metrics · Alarms", C.monitoring, C.monitoringBg)}
  ${box(260, 850, 140, 60, "X-Ray", "Traces", C.monitoring, C.monitoringBg)}
  ${box(440, 850, 160, 60, "CodePipeline", "CI/CD Pipeline", C.integration, C.integrationBg)}
  ${box(640, 850, 150, 60, "CodeBuild", "Test + Build", C.integration, C.integrationBg)}
  ${box(830, 850, 150, 60, "ECR", "Docker Images", C.compute, C.computeBg)}
  ${box(1020, 850, 160, 60, "EventBridge", "Scheduler · Events", C.monitoring, C.monitoringBg)}
  ${box(1220, 850, 140, 60, "SNS", "Notifications", C.monitoring, C.monitoringBg)}

  <!-- Logging arrows -->
  ${arrow(1020, 355, 1020, 845, "logs", C.monitoring, true)}
  ${arrow(1020, 315, 1020, 845, "", C.monitoring, true)}
  ${arrow(1020, 395, 1020, 845, "", C.monitoring, true)}
  ${arrow(260, 350, 260, 845, "", C.monitoring, true)}
  ${arrow(790, 880, 825, 880, "", C.integration)}
  ${arrow(600, 855, 715, 855, "", C.integration)}

  <!-- ===== KEY METRICS FOOTER ===== -->
  <rect x="30" y="950" width="1860" height="55" rx="8" fill="${C.layer2}" fill-opacity="0.4" stroke="${C.boxBorder}" stroke-width="0.5"/>
  <text x="50" y="968" fill="${C.muted}" font-size="10" font-family="${FONT}" font-weight="500">Infrastructure Cost: ~$19,500/mo (estimated) · SLA: 99.95% · RTO: 15 min · RPO: 5 min</text>
  <text x="50" y="990" fill="${C.muted}" font-size="10" font-family="${FONT}" font-weight="500">Architecture designed for 1M total users / 100K DAU / 10K peak concurrent sessions · Voice data flows via WebRTC (SRTP) directly between user ↔ Game Engine</text>
</svg>`;

const outPath = path.resolve(__dirname, "out", "diagram.svg");
fs.writeFileSync(outPath, svgContent, "utf-8");
console.log(`✅ SVG diagram written to ${outPath}`);
console.log(`   Size: ${(svgContent.length / 1024).toFixed(1)} KB`);
