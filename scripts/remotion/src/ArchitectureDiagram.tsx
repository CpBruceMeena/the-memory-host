import React from "react";
import { AbsoluteFill, useVideoConfig } from "remotion";

// ─── Color Palette ───────────────────────────────────────────────────────────
const COLORS = {
  bg: "#0B1426",
  grid: "#1A2744",
  text: "#E2E8F0",
  muted: "#94A3B8",
  accent: "#38BDF8",
  accentGlow: "#38BDF840",

  // AWS Service Colors
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

  // Data Flow
  flowLine: "#38BDF860",
  flowArrow: "#38BDF8",
  flowGlow: "#38BDF820",

  // Layer backgrounds
  layer1: "#0F1A36",
  layer2: "#141F3D",
  layer3: "#192844",
  layerBg: "#38BDF808",

  // Box styling
  boxBg: "#1E293B",
  boxBorder: "#334155",
  boxShadow: "#00000040",

  // User
  userBox: "#2D1B69",
  userBorder: "#8B5CF6",
};

// ─── Typography ──────────────────────────────────────────────────────────────
const FONT = "'Inter', 'SF Pro Display', -apple-system, sans-serif";
const FONT_MONO = "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace";

// ─── Dimensions ──────────────────────────────────────────────────────────────
const W = 1920;
const H = 1080;

// ─── AWS Service Box Component ───────────────────────────────────────────────

interface ServiceBoxProps {
  x: number;
  y: number;
  w: number;
  h: number;
  label: string;
  sublabel?: string;
  color: string;
  bgColor?: string;
  icon?: string;
  isHighlighted?: boolean;
}

const ServiceBox: React.FC<ServiceBoxProps> = ({
  x,
  y,
  w,
  h,
  label,
  sublabel,
  color,
  bgColor,
  icon,
  isHighlighted,
}) => (
  <g>
    {/* Glow background */}
    <rect
      x={x - 2}
      y={y - 2}
      width={w + 4}
      height={h + 4}
      rx={10}
      ry={10}
      fill={isHighlighted ? `${color}10` : "none"}
      stroke={isHighlighted ? `${color}30` : "none"}
      strokeWidth={1}
    />
    {/* Box */}
    <rect
      x={x}
      y={y}
      width={w}
      height={h}
      rx={8}
      ry={8}
      fill={bgColor || COLORS.boxBg}
      stroke={color}
      strokeWidth={isHighlighted ? 2 : 1}
      strokeOpacity={isHighlighted ? 0.9 : 0.6}
      filter="url(#shadow)"
    />
    {/* Top accent bar */}
    <rect
      x={x + 1}
      y={y + 1}
      width={w - 2}
      height={3}
      rx={2}
      fill={color}
      fillOpacity={0.7}
    />
    {/* Icon */}
    {icon && (
      <text
        x={x + 14}
        y={y + 28}
        fill={color}
        fontSize={18}
        fontFamily={FONT}
        textAnchor="middle"
        dominantBaseline="central"
      >
        {icon}
      </text>
    )}
    {/* Label */}
    <text
      x={x + w / 2}
      y={y + (sublabel ? 26 : 34)}
      fill={COLORS.text}
      fontSize={sublabel ? 13 : 14}
      fontFamily={FONT}
      fontWeight={600}
      textAnchor="middle"
      dominantBaseline="central"
    >
      {label}
    </text>
    {/* Sub-label */}
    {sublabel && (
      <text
        x={x + w / 2}
        y={y + 42}
        fill={COLORS.muted}
        fontSize={10}
        fontFamily={FONT_MONO}
        fontWeight={400}
        textAnchor="middle"
        dominantBaseline="central"
      >
        {sublabel}
      </text>
    )}
  </g>
);

// ─── Arrow Component ─────────────────────────────────────────────────────────

interface ArrowProps {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  label?: string;
  color?: string;
  dashed?: boolean;
  glow?: boolean;
}

const Arrow: React.FC<ArrowProps> = ({
  x1,
  y1,
  x2,
  y2,
  label,
  color = COLORS.flowLine,
  dashed = false,
  glow = false,
}) => {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.sqrt(dx * dx + dy * dy);
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);

  // Arrowhead
  const ax = x2;
  const ay = y2;

  return (
    <g>
      {/* Glow line */}
      {glow && (
        <line
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          stroke={color}
          strokeWidth={6}
          strokeOpacity={0.15}
          strokeDasharray={dashed ? "6,4" : "none"}
        />
      )}
      {/* Main line */}
      <line
        x1={x1}
        y1={y1}
        x2={x2}
        y2={y2}
        stroke={color}
        strokeWidth={2}
        strokeOpacity={0.8}
        strokeDasharray={dashed ? "6,4" : "none"}
      />
      {/* Arrowhead */}
      <polygon
        points={`${ax - 8},${ay - 5} ${ax},${ay} ${ax - 8},${ay + 5}`}
        fill={color}
        fillOpacity={0.8}
        transform={`rotate(${angle}, ${ax}, ${ay})`}
      />
      {/* Label */}
      {label && (
        <text
          x={(x1 + x2) / 2}
          y={(y1 + y2) / 2 - 10}
          fill={COLORS.muted}
          fontSize={9}
          fontFamily={FONT}
          fontWeight={500}
          textAnchor="middle"
          dominantBaseline="central"
        >
          {label}
        </text>
      )}
    </g>
  );
};

// ─── Layer Label ─────────────────────────────────────────────────────────────

interface LayerLabelProps {
  x: number;
  y: number;
  label: string;
  sublabel: string;
}

const LayerLabel: React.FC<LayerLabelProps> = ({ x, y, label, sublabel }) => (
  <g>
    <text
      x={x}
      y={y}
      fill={COLORS.text}
      fontSize={16}
      fontFamily={FONT}
      fontWeight={700}
      textAnchor="start"
      dominantBaseline="central"
    >
      {label}
    </text>
    <text
      x={x}
      y={y + 22}
      fill={COLORS.muted}
      fontSize={11}
      fontFamily={FONT}
      fontWeight={400}
      textAnchor="start"
      dominantBaseline="central"
    >
      {sublabel}
    </text>
  </g>
);

// ─── Metrics Card ────────────────────────────────────────────────────────────

interface MetricCardProps {
  x: number;
  y: number;
  label: string;
  value: string;
  color: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ x, y, label, value, color }) => (
  <g>
    <rect
      x={x}
      y={y}
      width={130}
      height={48}
      rx={6}
      fill={COLORS.boxBg}
      stroke={`${color}40`}
      strokeWidth={1}
    />
    <text
      x={x + 65}
      y={y + 16}
      fill={color}
      fontSize={15}
      fontFamily={FONT_MONO}
      fontWeight={700}
      textAnchor="middle"
      dominantBaseline="central"
    >
      {value}
    </text>
    <text
      x={x + 65}
      y={y + 33}
      fill={COLORS.muted}
      fontSize={9}
      fontFamily={FONT}
      fontWeight={500}
      textAnchor="middle"
      dominantBaseline="central"
    >
      {label}
    </text>
  </g>
);

// ─── Legend Item ─────────────────────────────────────────────────────────────

interface LegendItemProps {
  x: number;
  y: number;
  color: string;
  label: string;
}

const LegendItem: React.FC<LegendItemProps> = ({ x, y, color, label }) => (
  <g>
    <rect x={x} y={y - 5} width={12} height={12} rx={2} fill={color} fillOpacity={0.3} stroke={color} strokeWidth={1} />
    <text
      x={x + 18}
      y={y + 1}
      fill={COLORS.text}
      fontSize={10}
      fontFamily={FONT}
      fontWeight={500}
      textAnchor="start"
      dominantBaseline="central"
    >
      {label}
    </text>
  </g>
);

// ─── Region badge ────────────────────────────────────────────────────────────

const RegionBadge: React.FC<{ x: number; y: number }> = ({ x, y }) => (
  <g>
    <rect x={x} y={y} width={100} height={22} rx={11} fill={COLORS.boxBg} stroke={COLORS.boxBorder} strokeWidth={1} />
    <text
      x={x + 50}
      y={y + 11}
      fill={COLORS.accent}
      fontSize={10}
      fontFamily={FONT_MONO}
      fontWeight={600}
      textAnchor="middle"
      dominantBaseline="central"
    >
      eu-west-1
    </text>
  </g>
);

// ─── Title Block ─────────────────────────────────────────────────────────────

const TitleBlock: React.FC = () => (
  <g>
    {/* Logo / Brand */}
    <rect x={30} y={20} width={44} height={44} rx={12} fill={COLORS.accent} fillOpacity={0.15} stroke={COLORS.accent} strokeWidth={1} />
    <text x={52} y={42} fill={COLORS.accent} fontSize={22} fontFamily={FONT} fontWeight={800} textAnchor="middle" dominantBaseline="central">
      MH
    </text>

    {/* Title */}
    <text x={90} y={35} fill={COLORS.text} fontSize={20} fontFamily={FONT} fontWeight={700}>
      The Memory Host — AWS Architecture
    </text>
    <text x={90} y={55} fill={COLORS.muted} fontSize={12} fontFamily={FONT} fontWeight={400}>
      Real-time voice memory game · 1M Total Users · 100K Daily Active Users · 10K Peak Concurrent
    </text>

    {/* Metrics */}
    <MetricCard x={1300} y={18} label="Avg Latency (STT→TTS)" value="&lt;1.2s" color={COLORS.accent} />
    <MetricCard x={1440} y={18} label="Peak Sessions" value="10K" color={COLORS.compute} />
    <MetricCard x={1580} y={18} label="Daily Game Rounds" value="500K" color={COLORS.integration} />
    <MetricCard x={1720} y={18} label="Data Ingest / Day" value="~150GB" color={COLORS.database} />

    {/* Region */}
    <RegionBadge x={1720} y={1030} />
  </g>
);

// ─── Main Diagram Component ──────────────────────────────────────────────────

export const ArchitectureDiagram: React.FC = () => {
  const { width, height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundImage: `linear-gradient(135deg, ${COLORS.bg} 0%, #0D1A2D 50%, ${COLORS.bg} 100%)` }}>
      <svg viewBox={`0 0 ${W} ${H}`} width={width} height={height} style={{ background: "transparent" }}>
        <defs>
          {/* Grid pattern */}
          <pattern id="grid" width={40} height={40} patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke={COLORS.grid} strokeWidth={0.5} strokeOpacity={0.3} />
          </pattern>
          {/* Shadow filter */}
          <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx={0} dy={2} stdDeviation={4} floodColor={COLORS.boxShadow} floodOpacity={0.5} />
          </filter>
          {/* Glow filter */}
          <filter id="glow">
            <feGaussianBlur stdDeviation={3} result="coloredBlur" />
            <feMerge>
              <feMergeNode in="coloredBlur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Gradient for connection lines */}
          <linearGradient id="flowGradUp" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor={COLORS.flowLine} stopOpacity={0.3} />
            <stop offset="100%" stopColor={COLORS.flowArrow} stopOpacity={0.9} />
          </linearGradient>
          {/* Gradient for user */}
          <linearGradient id="userGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={COLORS.userBox} />
            <stop offset="100%" stopColor="#1A1050" />
          </linearGradient>
        </defs>

        {/* Background grid */}
        <rect width={W} height={H} fill="url(#grid)" />

        {/* ===== CONTENT ===== */}
        {/* Title & Metrics */}
        <TitleBlock />

        {/* Legend */}
        <LegendItem x={30} y={1050} color={COLORS.compute} label="Compute / Container" />
        <LegendItem x={190} y={1050} color={COLORS.network} label="Networking / CDN" />
        <LegendItem x={360} y={1050} color={COLORS.database} label="Database / Storage" />
        <LegendItem x={530} y={1050} color={COLORS.security} label="Security / WAF" />
        <LegendItem x={700} y={1050} color={COLORS.monitoring} label="Monitoring / Observability" />
        <LegendItem x={910} y={1050} color={COLORS.integration} label="Integration / CI-CD" />
        <LegendItem x={1100} y={1050} color={COLORS.storage} label="Object Storage" />

        {/* ===== LAYER 1: User / Edge (y: 80-200) ===== */}
        <rect x={20} y={80} width={1880} height={120} rx={12} fill={COLORS.layer1} fillOpacity={0.5} stroke={COLORS.layerBg} strokeWidth={1} />
        <LayerLabel x={36} y={98} label="👤 User &amp; Edge" sublabel="DNS · CDN · DDoS Protection" />

        {/* User browser */}
        <rect x={60} y={125} width={150} height={58} rx={10} fill="url(#userGrad)" stroke={COLORS.userBorder} strokeWidth={1.5} filter="url(#shadow)" />
        <text x={135} y={152} fill={COLORS.text} fontSize={22} fontFamily={FONT} textAnchor="middle" dominantBaseline="central">
          🌐
        </text>
        <text x={135} y={171} fill={COLORS.text} fontSize={12} fontFamily={FONT} fontWeight={600} textAnchor="middle" dominantBaseline="central">
          User Browser
        </text>

        {/* Route 53 */}
        <ServiceBox x={350} y={120} w={150} h={58} label="Route 53" sublabel="DNS · Latency-based" color={COLORS.network} bgColor={COLORS.networkBg} />

        {/* CloudFront + WAF */}
        <ServiceBox x={560} y={120} w={190} h={58} label="CloudFront + WAF" sublabel="CDN · SSL · Rate Limit" color={COLORS.security} bgColor={COLORS.securityBg} />

        {/* Arrows from User → Route53 → CloudFront */}
        <Arrow x1={210} y1={155} x2={345} y2={155} label="HTTPS" color={COLORS.network} />
        <Arrow x1={500} y1={155} x2={555} y2={155} label="" color={COLORS.network} />

        {/* ===== LAYER 2: Application (y: 230-520) ===== */}
        <rect x={20} y={230} width={1880} height={290} rx={12} fill={COLORS.layer2} fillOpacity={0.5} stroke={COLORS.layerBg} strokeWidth={1} />
        <LayerLabel x={36} y={248} label="⚙️ Application Layer" sublabel="ECS Fargate · Auto Scaling · Load Balancers" />

        {/* ALB for HTTP services */}
        <ServiceBox x={60} y={280} w={180} h={60} label="ALB" sublabel="HTTPS Ingress" color={COLORS.network} bgColor={COLORS.networkBg} isHighlighted />

        {/* NLB for WebSocket/Signaling */}
        <ServiceBox x={60} y={365} w={180} h={60} label="NLB" sublabel="WebSocket Passthrough" color={COLORS.network} bgColor={COLORS.networkBg} />

        {/* Next.js Frontend */}
        <ServiceBox x={310} y={275} w={180} h={75} label="Next.js Frontend" sublabel="Port 3000 · 8 tasks" color={COLORS.compute} bgColor={COLORS.computeBg} />
        <text x={400} y={372} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          12x Fargate tasks · min 6
        </text>

        {/* REST API */}
        <ServiceBox x={530} y={275} w={180} h={75} label="REST API" sublabel="Port 8000 · FastAPI" color={COLORS.compute} bgColor={COLORS.computeBg} />
        <text x={620} y={372} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          8x Fargate tasks · min 4
        </text>

        {/* WebSocket Signaling Server */}
        <ServiceBox x={750} y={355} w={180} h={65} label="Signaling Server" sublabel="Port 3001 · WebSocket" color={COLORS.compute} bgColor={COLORS.computeBg} />
        <text x={840} y={438} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          6x Fargate tasks · sticky-ws
        </text>

        {/* Game Engine (Pipecat Bots) */}
        <ServiceBox x={1000} y={275} w={220} h={95} label="🎙️ Game Engine" sublabel="Pipecat Bots · Port 3002" color={COLORS.integration} bgColor={COLORS.integrationBg} isHighlighted />
        <text x={1110} y={392} fill={COLORS.compute} fontSize={10} fontFamily={FONT_MONO} fontWeight={600} textAnchor="middle">
          {">10K concurrent bot pipelines"}
        </text>
        {/* Stack icon for bot pipelines */}
        <text x={1110} y={358} fill={COLORS.integration} fontSize={11} fontFamily={FONT} textAnchor="middle" dominantBaseline="central">
          Each session = 1 Pipecat Pipeline
        </text>

        {/* TURN Server */}
        <ServiceBox x={1280} y={355} w={180} h={65} label="Coturn TURN" sublabel="WebRTC NAT Traversal" color={COLORS.network} bgColor={COLORS.networkBg} />
        <text x={1370} y={438} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          EC2 c6i.large × 4 (ASG)
        </text>

        {/* ECS Cluster label */}
        <rect x={310} y={265} width={910} height={20} rx={4} fill={COLORS.compute} fillOpacity={0.08} stroke={COLORS.compute} strokeWidth={0.5} />
        <text x={765} y={278} fill={COLORS.compute} fontSize={10} fontFamily={FONT_MONO} fontWeight={600} textAnchor="middle" dominantBaseline="central">
          Amazon ECS Cluster — Fargate (ARM64)
        </text>

        {/* ===== DATA FLOW ARROWS (Application Layer) ===== */}

        {/* CloudFront → ALB */}
        <Arrow x1={750} y1={150} x2={750} y2={275} label="HTTPS" color={COLORS.network} />

        {/* ALB → Next.js, ALB → REST API */}
        <Arrow x1={240} y1={310} x2={305} y2={310} label="" />
        <Arrow x1={240} y1={315} x2={525} y2={315} label="/api/* → BFF" color={COLORS.compute} />

        {/* Next.js BFF → REST API */}
        <Arrow x1={490} y1={310} x2={525} y2={310} label="" color={COLORS.compute} />

        {/* REST API → Game Engine */}
        <Arrow x1={710} y1={315} x2={995} y2={315} label="POST /start-session" color={COLORS.integration} dashed />

        {/* NLB → Signaling Server */}
        <Arrow x1={240} y1={395} x2={745} y2={395} label="WebSocket" color={COLORS.network} />
        {/* Signaling → Game Engine */}
        <Arrow x1={930} y1={390} x2={995} y2={370} label="ws:3001" color={COLORS.flowArrow} />

        {/* Game Engine ↔ TURN */}
        <Arrow x1={1220} y1={365} x2={1275} y2={390} label="TURN relay" color={COLORS.network} dashed />

        {/* User ↔ Game Engine (WebRTC) — direct path */}
        <Arrow x1={135} y1={183} x2={1110} y2={270} label="WebRTC (SRTP) Audio" color={COLORS.integration} glow />
        {/* User ↔ Signaling — WebSocket path */}
        <Arrow x1={135} y1={188} x2={840} y2={350} label="Signaling WS" color={COLORS.network} dashed />

        {/* ===== LAYER 3: Data & Persistence (y: 550-780) ===== */}
        <rect x={20} y={550} width={1880} height={230} rx={12} fill={COLORS.layer3} fillOpacity={0.5} stroke={COLORS.layerBg} strokeWidth={1} />
        <LayerLabel x={36} y={568} label="🗄️ Data &amp; Persistence" sublabel="Multi-AZ · Read Replicas · Caching" />

        {/* RDS Aurora PostgreSQL - Primary */}
        <ServiceBox x={60} y={595} w={220} h={80} label="Aurora PostgreSQL" sublabel="Primary (writer)" color={COLORS.database} bgColor={COLORS.databaseBg} isHighlighted />
        <text x={170} y={695} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          db.r7g.large · Multi-AZ
        </text>

        {/* RDS Aurora - Reader */}
        <ServiceBox x={320} y={595} w={200} h={80} label="Aurora Read Replica" sublabel="5 x db.r7g.large" color={COLORS.database} bgColor={COLORS.databaseBg} />
        <text x={420} y={695} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          Auto-scaling replicas
        </text>

        {/* ElastiCache Redis - Session cache */}
        <ServiceBox x={580} y={595} w={200} h={80} label="ElastiCache Redis" sublabel="Session + Leaderboard" color={COLORS.database} bgColor={COLORS.databaseBg} />
        <text x={680} y={695} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle">
          cache.r7g.large · cluster
        </text>

        {/* S3 - Assets */}
        <ServiceBox x={840} y={595} w={200} h={80} label="S3 Static Assets" sublabel="Logs · Build Artifacts" color={COLORS.storage} bgColor={COLORS.storageBg} />

        {/* Deepgram Cloud (External) */}
        <g>
          <rect x={1100} y={595} w={220} h={80} rx={8} fill={COLORS.integrationBg} stroke={COLORS.integration} strokeWidth={1} strokeDasharray="6,3" filter="url(#shadow)" />
          <text x={1210} y={622} fill={COLORS.integration} fontSize={14} fontFamily={FONT} fontWeight={600} textAnchor="middle" dominantBaseline="central">
            ☁️ Deepgram Cloud
          </text>
          <text x={1210} y={642} fill={COLORS.text} fontSize={11} fontFamily={FONT} textAnchor="middle" dominantBaseline="central">
            Nova-2 STT · Aura-2 TTS
          </text>
          <text x={1210} y={660} fill={COLORS.muted} fontSize={9} fontFamily={FONT} textAnchor="middle" dominantBaseline="central">
            ~100K API calls / peak hour
          </text>
        </g>

        {/* Data flow to database */}
        <Arrow x1={490} y1={355} x2={490} y2={590} label="reads polls" color={COLORS.database} />
        <Arrow x1={1110} y1={375} x2={1110} y2={590} label="writes scores" color={COLORS.database} />

        {/* REST API → Aurora Reader */}
        <Arrow x1={620} y1={355} x2={420} y2={590} label="" color={COLORS.database} />

        {/* Game Engine → Aurora Primary */}
        <Arrow x1={1110} y1={370} x2={170} y2={590} label="" color={COLORS.database} />

        {/* Redis connections */}
        <Arrow x1={680} y1={355} x2={680} y2={590} label="cache" color={COLORS.database} dashed />

        {/* Game Engine → Deepgram */}
        <Arrow x1={1220} y1={375} x2={1220} y2={590} label="STT/TTS API" color={COLORS.integration} dashed />

        {/* ===== LAYER 4: Observability & CI/CD (y: 810-920) ===== */}
        <rect x={20} y={810} width={1880} height={120} rx={12} fill={COLORS.layer1} fillOpacity={0.3} stroke={COLORS.layerBg} strokeWidth={1} />
        <LayerLabel x={36} y={830} label="📊 Observability &amp; CI/CD" sublabel="Monitoring · Logging · Deployment" />

        {/* CloudWatch */}
        <ServiceBox x={60} y={850} w={160} h={60} label="CloudWatch" sublabel="Logs · Metrics · Alarms" color={COLORS.monitoring} bgColor={COLORS.monitoringBg} />

        {/* X-Ray */}
        <ServiceBox x={260} y={850} w={140} h={60} label="X-Ray" sublabel="Traces" color={COLORS.monitoring} bgColor={COLORS.monitoringBg} />

        {/* CodePipeline */}
        <ServiceBox x={440} y={850} w={160} h={60} label="CodePipeline" sublabel="CI/CD Pipeline" color={COLORS.integration} bgColor={COLORS.integrationBg} />

        {/* CodeBuild */}
        <ServiceBox x={640} y={850} w={150} h={60} label="CodeBuild" sublabel="Test + Build" color={COLORS.integration} bgColor={COLORS.integrationBg} />

        {/* ECR */}
        <ServiceBox x={830} y={850} w={150} h={60} label="ECR" sublabel="Docker Images" color={COLORS.compute} bgColor={COLORS.computeBg} />

        {/* EventBridge */}
        <ServiceBox x={1020} y={850} w={160} h={60} label="EventBridge" sublabel="Scheduler · Events" color={COLORS.monitoring} bgColor={COLORS.monitoringBg} />

        {/* SNS */}
        <ServiceBox x={1220} y={850} w={140} h={60} label="SNS" sublabel="Notifications" color={COLORS.monitoring} bgColor={COLORS.monitoringBg} />

        {/* CloudWatch logs from services */}
        <Arrow x1={1020} y1={355} x2={1020} y2={845} label="logs" color={COLORS.monitoring} dashed />
        <Arrow x1={1020} y1={315} x2={1020} y2={845} color={COLORS.monitoring} dashed />
        <Arrow x1={1020} y1={395} x2={1020} y2={845} color={COLORS.monitoring} dashed />
        <Arrow x1={260} y1={350} x2={260} y2={845} color={COLORS.monitoring} dashed />

        {/* Pipeline → ECR */}
        <Arrow x1={790} y1={880} x2={825} y2={880} color={COLORS.integration} />
        <Arrow x1={600} y1={855} x2={715} y2={855} color={COLORS.integration} />

        {/* ===== KEY METRICS FOOTER ===== */}
        <rect x={30} y={950} width={1860} height={55} rx={8} fill={COLORS.layer2} fillOpacity={0.4} stroke={COLORS.boxBorder} strokeWidth={0.5} />
        <text x={50} y={968} fill={COLORS.muted} fontSize={10} fontFamily={FONT} fontWeight={500}>
          Infrastructure Cost: ~$19,500/mo (estimated) · SLA: 99.95% · RTO: 15 min · RPO: 5 min
        </text>
        <text x={50} y={990} fill={COLORS.muted} fontSize={10} fontFamily={FONT} fontWeight={500}>
          Architecture designed for 1M total users / 100K DAU / 10K peak concurrent sessions · Voice data flows via WebRTC (SRTP) directly between user ↔ Game Engine
        </text>
      </svg>
    </AbsoluteFill>
  );
};
