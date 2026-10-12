import React from 'react';

/**
 * Pixel-exact vector SVG icons matching the HydraControl 3D / skeuomorphic mobile design
 */

// 1. Motor Icon (3D Industrial Electric Motor with metallic cooling fins, shaft & mount)
export const MotorIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="motor-body-3d" x1="20" y1="25" x2="80" y2="75" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#94a3b8" />
        <stop offset="25%" stopColor="#cbd5e1" />
        <stop offset="55%" stopColor="#64748b" />
        <stop offset="85%" stopColor="#475569" />
        <stop offset="100%" stopColor="#334155" />
      </linearGradient>
      <linearGradient id="motor-fin-light" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#f1f5f9" />
        <stop offset="100%" stopColor="#64748b" />
      </linearGradient>
      <linearGradient id="motor-shaft-grad" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#e2e8f0" />
        <stop offset="50%" stopColor="#94a3b8" />
        <stop offset="100%" stopColor="#475569" />
      </linearGradient>
      <linearGradient id="motor-box-grad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#cbd5e1" />
        <stop offset="100%" stopColor="#475569" />
      </linearGradient>
      <filter id="motor-drop-shadow" x="5" y="70" width="90" height="25" filterUnits="userSpaceOnUse">
        <feGaussianBlur stdDeviation="3" />
      </filter>
    </defs>

    {/* Drop shadow on ground */}
    <ellipse cx="50" cy="80" rx="36" ry="6" fill="#0f172a" fillOpacity="0.25" filter="url(#motor-drop-shadow)" />

    {/* Mounting Base / Feet */}
    <rect x="24" y="68" width="56" height="8" rx="2" fill="#334155" />
    <path d="M22 76H82L80 78H24L22 76Z" fill="#1e293b" />
    <rect x="28" y="72" width="10" height="3" rx="1.5" fill="#94a3b8" />
    <rect x="66" y="72" width="10" height="3" rx="1.5" fill="#94a3b8" />

    {/* Left Output Shaft */}
    <rect x="10" y="47" width="14" height="10" rx="2" fill="url(#motor-shaft-grad)" stroke="#475569" strokeWidth="1" />
    <circle cx="10" cy="52" r="5" fill="#64748b" />
    <circle cx="10" cy="52" r="2.5" fill="#334155" />
    <rect x="12" y="49" width="4" height="2" fill="#334155" />

    {/* Front Bearing Housing Collar */}
    <ellipse cx="24" cy="52" rx="5" ry="17" fill="#64748b" />
    <ellipse cx="23" cy="52" rx="4" ry="15" fill="#94a3b8" />

    {/* Motor Main Cylinder Body */}
    <rect x="24" y="34" width="52" height="36" rx="4" fill="url(#motor-body-3d)" />

    {/* Cooling Fins (Horizontal 3D Grooves) */}
    <rect x="27" y="37" width="46" height="3" rx="1.5" fill="url(#motor-fin-light)" opacity="0.9" />
    <rect x="27" y="40" width="46" height="1.5" fill="#1e293b" opacity="0.6" />

    <rect x="27" y="43" width="46" height="3" rx="1.5" fill="url(#motor-fin-light)" opacity="0.9" />
    <rect x="27" y="46" width="46" height="1.5" fill="#1e293b" opacity="0.6" />

    <rect x="27" y="49" width="46" height="3" rx="1.5" fill="url(#motor-fin-light)" opacity="0.9" />
    <rect x="27" y="52" width="46" height="1.5" fill="#1e293b" opacity="0.6" />

    <rect x="27" y="55" width="46" height="3" rx="1.5" fill="url(#motor-fin-light)" opacity="0.9" />
    <rect x="27" y="58" width="46" height="1.5" fill="#1e293b" opacity="0.6" />

    <rect x="27" y="61" width="46" height="3" rx="1.5" fill="url(#motor-fin-light)" opacity="0.9" />
    <rect x="27" y="64" width="46" height="1.5" fill="#1e293b" opacity="0.6" />

    {/* Rear Fan Shroud / Endbell */}
    <path d="M76 34C80 34 83 37 83 41V63C83 67 80 70 76 70V34Z" fill="#475569" />
    <path d="M78 37C81 37 83 39 83 43V61C83 65 81 67 78 67V37Z" fill="#334155" />
    {/* Rear ventilation grille lines */}
    <line x1="80" y1="42" x2="80" y2="62" stroke="#64748b" strokeWidth="1.5" />
    <line x1="82" y1="45" x2="82" y2="59" stroke="#64748b" strokeWidth="1.5" />

    {/* Top Terminal Conduit Box */}
    <rect x="42" y="24" width="22" height="11" rx="2.5" fill="url(#motor-box-grad)" stroke="#334155" strokeWidth="1" />
    <rect x="44" y="25" width="18" height="3" rx="1" fill="#f1f5f9" opacity="0.7" />
    <circle cx="45" cy="31" r="1.5" fill="#1e293b" />
    <circle cx="61" cy="31" r="1.5" fill="#1e293b" />
  </svg>
);

// 2. Interlocks Padlock Icon (Glossy Emerald Green Padlock with Chrome Shackle)
export const InterlockIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="shackle-metal" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#94a3b8" />
        <stop offset="30%" stopColor="#f8fafc" />
        <stop offset="70%" stopColor="#cbd5e1" />
        <stop offset="100%" stopColor="#64748b" />
      </linearGradient>
      <linearGradient id="padlock-green" x1="25" y1="35" x2="75" y2="85" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#10b981" />
        <stop offset="50%" stopColor="#059669" />
        <stop offset="100%" stopColor="#047857" />
      </linearGradient>
      <linearGradient id="padlock-highlight" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.6" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>

    {/* Shackle (Silver metallic arch) */}
    <path
      d="M34 44V28C34 19.1634 41.1634 12 50 12C58.8366 12 66 19.1634 66 28V44"
      stroke="url(#shackle-metal)"
      strokeWidth="10"
      strokeLinecap="round"
    />
    <path
      d="M34 44V28C34 19.1634 41.1634 12 50 12C58.8366 12 66 19.1634 66 28V44"
      stroke="#475569"
      strokeWidth="1.5"
      strokeLinecap="round"
    />

    {/* Padlock Body (Rounded green capsule) */}
    <rect x="24" y="40" width="52" height="46" rx="12" fill="url(#padlock-green)" />
    
    {/* Bevel highlight */}
    <rect x="26" y="42" width="48" height="20" rx="10" fill="url(#padlock-highlight)" />

    {/* Keyhole (White / silver keyhole) */}
    <circle cx="50" cy="58" r="5" fill="#ffffff" />
    <path d="M47.5 58L46 72H54L52.5 58H47.5Z" fill="#ffffff" />
    <circle cx="50" cy="58" r="2.5" fill="#047857" opacity="0.3" />
  </svg>
);

// 3. Tank Level Icon (Stainless Steel Tank with Viewing Window & Blue Water)
export const TankLevelIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="tank-steel" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#94a3b8" />
        <stop offset="25%" stopColor="#f1f5f9" />
        <stop offset="60%" stopColor="#cbd5e1" />
        <stop offset="100%" stopColor="#64748b" />
      </linearGradient>
      <linearGradient id="tank-water-fill" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#0284c7" />
        <stop offset="35%" stopColor="#38bdf8" />
        <stop offset="70%" stopColor="#0284c7" />
        <stop offset="100%" stopColor="#0369a1" />
      </linearGradient>
      <linearGradient id="glass-glare" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
        <stop offset="50%" stopColor="#ffffff" stopOpacity="0.1" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>

    {/* Tank Leg Stand */}
    <rect x="30" y="80" width="4" height="8" rx="1" fill="#475569" />
    <rect x="66" y="80" width="4" height="8" rx="1" fill="#475569" />
    <rect x="48" y="80" width="4" height="8" rx="1" fill="#334155" />

    {/* Dome Top Cap */}
    <ellipse cx="50" cy="22" rx="26" ry="7" fill="url(#tank-steel)" />
    <ellipse cx="50" cy="18" rx="6" ry="2.5" fill="#475569" />
    <rect x="48" y="14" width="4" height="5" rx="1" fill="#64748b" />

    {/* Tank Steel Outer Shell */}
    <rect x="24" y="22" width="52" height="60" rx="3" fill="url(#tank-steel)" />

    {/* Transparent / Cutaway Water Window Inside */}
    <rect x="28" y="26" width="44" height="52" rx="2" fill="#e0f2fe" />
    
    {/* Water Fill Level (Vibrant 3D Blue Liquid) */}
    <path
      d="M28 42C33 40 38 43 43 41C48 39 54 43 60 41C66 39 70 42 72 41V76C72 77.1 71.1 78 70 78H30C28.9 78 28 77.1 28 76V42Z"
      fill="url(#tank-water-fill)"
    />

    {/* Glass Reflection Glare */}
    <path d="M30 28L46 28L36 76L30 76V28Z" fill="url(#glass-glare)" />

    {/* Steel Ladder on Right Side */}
    <rect x="70" y="18" width="3" height="66" rx="1.5" fill="#475569" />
    <line x1="66" y1="26" x2="73" y2="26" stroke="#334155" strokeWidth="2" />
    <line x1="66" y1="36" x2="73" y2="36" stroke="#334155" strokeWidth="2" />
    <line x1="66" y1="46" x2="73" y2="46" stroke="#334155" strokeWidth="2" />
    <line x1="66" y1="56" x2="73" y2="56" stroke="#334155" strokeWidth="2" />
    <line x1="66" y1="66" x2="73" y2="66" stroke="#334155" strokeWidth="2" />
    <line x1="66" y1="76" x2="73" y2="76" stroke="#334155" strokeWidth="2" />

    {/* Horizontal Steel Reinforcement Rings */}
    <line x1="24" y1="36" x2="68" y2="36" stroke="#94a3b8" strokeWidth="1.5" />
    <line x1="24" y1="52" x2="68" y2="52" stroke="#94a3b8" strokeWidth="1.5" />
    <line x1="24" y1="68" x2="68" y2="68" stroke="#94a3b8" strokeWidth="1.5" />

    {/* Bottom Base Rim */}
    <ellipse cx="50" cy="82" rx="26" ry="4" fill="#475569" />
  </svg>
);

// 4. Sump Level Icon (Submersible Sensor Probe with Curving Cable into 3 Water Waves)
export const SumpLevelIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="probe-body" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#475569" />
        <stop offset="40%" stopColor="#1e293b" />
        <stop offset="70%" stopColor="#0f172a" />
        <stop offset="100%" stopColor="#334155" />
      </linearGradient>
      <linearGradient id="wave-grad-1" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#38bdf8" />
        <stop offset="100%" stopColor="#0284c7" />
      </linearGradient>
      <linearGradient id="wave-grad-2" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#0ea5e9" />
        <stop offset="100%" stopColor="#0369a1" />
      </linearGradient>
      <linearGradient id="wave-grad-3" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stopColor="#0284c7" />
        <stop offset="100%" stopColor="#1e40af" />
      </linearGradient>
    </defs>

    {/* Cable curving down from top */}
    <path
      d="M58 12C58 20 48 18 48 26V35"
      stroke="#1e293b"
      strokeWidth="4"
      strokeLinecap="round"
    />

    {/* Cable Relief Boot / Grommet */}
    <path d="M45 32H51L53 38H43L45 32Z" fill="#334155" />

    {/* Hydrostatic Sump Sensor Probe Body */}
    <rect x="42" y="38" width="12" height="30" rx="4" fill="url(#probe-body)" />
    <rect x="43" y="40" width="2" height="26" rx="1" fill="#94a3b8" opacity="0.6" />
    <circle cx="48" cy="65" r="2" fill="#38bdf8" />

    {/* 3 Layered Dynamic Water Ripple Waves */}
    {/* Wave 1 (Top) */}
    <path
      d="M18 52C23 48 28 48 33 52C38 56 43 56 48 52C53 48 58 48 63 52C68 56 73 56 78 52C80 50 82 50 84 52"
      stroke="url(#wave-grad-1)"
      strokeWidth="4"
      strokeLinecap="round"
    />

    {/* Wave 2 (Middle) */}
    <path
      d="M16 63C21 59 26 59 31 63C36 67 41 67 46 63C51 59 56 59 61 63C66 67 71 67 76 63C80 60 83 60 86 63"
      stroke="url(#wave-grad-2)"
      strokeWidth="4"
      strokeLinecap="round"
    />

    {/* Wave 3 (Bottom) */}
    <path
      d="M18 74C23 70 28 70 33 74C38 78 43 78 48 74C53 70 58 70 63 74C68 78 73 78 78 74C81 72 83 72 85 74"
      stroke="url(#wave-grad-3)"
      strokeWidth="3.5"
      strokeLinecap="round"
    />
  </svg>
);

// 5. Flow Rate Icon (Industrial Dial Pressure/Flow Gauge with Red Needle & Pipe)
export const FlowRateIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="gauge-bezel" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#cbd5e1" />
        <stop offset="50%" stopColor="#94a3b8" />
        <stop offset="100%" stopColor="#475569" />
      </linearGradient>
      <linearGradient id="pipe-metal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#94a3b8" />
        <stop offset="50%" stopColor="#cbd5e1" />
        <stop offset="100%" stopColor="#475569" />
      </linearGradient>
    </defs>

    {/* Horizontal Flow Pipe with Flanges */}
    <rect x="18" y="70" width="64" height="12" rx="2" fill="url(#pipe-metal)" />
    <rect x="18" y="68" width="6" height="16" rx="2" fill="#475569" />
    <rect x="76" y="68" width="6" height="16" rx="2" fill="#475569" />

    {/* Vertical Neck connector to gauge */}
    <rect x="45" y="52" width="10" height="20" rx="1" fill="url(#pipe-metal)" />
    <rect x="42" y="58" width="16" height="4" rx="1" fill="#475569" />

    {/* Outer Gauge Bezel Ring */}
    <circle cx="50" cy="38" r="26" fill="url(#gauge-bezel)" stroke="#334155" strokeWidth="1" />
    <circle cx="50" cy="38" r="23" fill="#ffffff" />
    <circle cx="50" cy="38" r="22" stroke="#cbd5e1" strokeWidth="1" />

    {/* Gauge Dial Tick Marks */}
    <line x1="50" y1="19" x2="50" y2="23" stroke="#1e293b" strokeWidth="2" strokeLinecap="round" />
    <line x1="37" y1="23" x2="40" y2="26" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="63" y1="23" x2="60" y2="26" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="29" y1="33" x2="33" y2="35" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="71" y1="33" x2="67" y2="35" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="31" y1="46" x2="35" y2="44" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />
    <line x1="69" y1="46" x2="65" y2="44" stroke="#1e293b" strokeWidth="1.5" strokeLinecap="round" />

    {/* Red warning zone arc on top-right */}
    <path
      d="M50 21C58 21 65 26 68 34"
      stroke="#ef4444"
      strokeWidth="2.5"
      strokeLinecap="round"
    />

    {/* Center Pin */}
    <circle cx="50" cy="38" r="4" fill="#334155" />

    {/* Bright Red Needle Pointing Up-Right (~2 o'clock) */}
    <line x1="50" y1="38" x2="65" y2="25" stroke="#dc2626" strokeWidth="2.5" strokeLinecap="round" />
    <circle cx="50" cy="38" r="2" fill="#dc2626" />
  </svg>
);

// 6. Water Quality Droplet Icon (Glossy 3D Pure Royal Blue Droplet with Curved Highlight)
export const WaterQualityIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="droplet-3d" x1="20" y1="15" x2="80" y2="85" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stopColor="#60a5fa" />
        <stop offset="35%" stopColor="#2563eb" />
        <stop offset="75%" stopColor="#1d4ed8" />
        <stop offset="100%" stopColor="#1e3a8a" />
      </linearGradient>
      <linearGradient id="droplet-gloss" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#ffffff" stopOpacity="0.8" />
        <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
      </linearGradient>
    </defs>

    {/* Main 3D Droplet */}
    <path
      d="M50 14C50 14 26 44 26 62C26 75.2548 36.7452 86 50 86C63.2548 86 74 75.2548 74 62C74 44 50 14 50 14Z"
      fill="url(#droplet-3d)"
    />

    {/* Curving Left Gloss / Specular Reflection */}
    <path
      d="M38 58C38 48 45 36 49 28C49 28 41 38 41 52C41 58 43 64 47 68C42 66 38 62 38 58Z"
      fill="url(#droplet-gloss)"
    />

    {/* Tiny Bottom Right Glow Spot */}
    <circle cx="58" cy="72" r="3" fill="#93c5fd" opacity="0.5" />
  </svg>
);

// 7. Electrical Load Panel Icon (3D Enclosure Box with Golden Lightning Bolt)
export const ElectricalLoadIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="panel-metal" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stopColor="#f1f5f9" />
        <stop offset="50%" stopColor="#cbd5e1" />
        <stop offset="100%" stopColor="#94a3b8" />
      </linearGradient>
      <linearGradient id="bolt-gold" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#fbbf24" />
        <stop offset="100%" stopColor="#f59e0b" />
      </linearGradient>
      <filter id="bolt-glow" x="20" y="20" width="60" height="60" filterUnits="userSpaceOnUse">
        <feGaussianBlur stdDeviation="2" />
      </filter>
    </defs>

    {/* Outer Enclosure Box */}
    <rect x="24" y="20" width="52" height="62" rx="8" fill="url(#panel-metal)" stroke="#64748b" strokeWidth="2" />

    {/* Left Hinges */}
    <rect x="22" y="30" width="3" height="8" rx="1.5" fill="#475569" />
    <rect x="22" y="64" width="3" height="8" rx="1.5" fill="#475569" />

    {/* Right Door Handle / Quarter-turn latch */}
    <rect x="73" y="48" width="4" height="8" rx="1" fill="#475569" />
    <circle cx="75" cy="52" r="1.5" fill="#94a3b8" />

    {/* Inset Door Panel */}
    <rect x="30" y="26" width="40" height="50" rx="5" fill="#e2e8f0" stroke="#94a3b8" strokeWidth="1" />

    {/* Glowing Orange/Gold Lightning Bolt */}
    <path
      d="M52 32L40 50H50L46 68L62 46H50L54 32H52Z"
      fill="#f59e0b"
      opacity="0.4"
      filter="url(#bolt-glow)"
    />
    <path
      d="M52 32L40 50H50L46 68L62 46H50L54 32H52Z"
      fill="url(#bolt-gold)"
      stroke="#d97706"
      strokeWidth="1.5"
      strokeLinejoin="round"
    />
  </svg>
);

// 8. Pump Schedules Icon (Royal Blue Calendar with Clock Badge)
export const PumpScheduleIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="cal-blue" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#2563eb" />
        <stop offset="100%" stopColor="#1d4ed8" />
      </linearGradient>
    </defs>

    {/* Calendar Body */}
    <rect x="22" y="24" width="52" height="52" rx="10" fill="url(#cal-blue)" />

    {/* Top Binder Rings */}
    <rect x="32" y="16" width="6" height="12" rx="3" fill="#1e3a8a" />
    <rect x="33" y="17" width="4" height="4" rx="2" fill="#93c5fd" />
    <rect x="58" y="16" width="6" height="12" rx="3" fill="#1e3a8a" />
    <rect x="59" y="17" width="4" height="4" rx="2" fill="#93c5fd" />

    {/* White Grid Days */}
    <rect x="30" y="38" width="7" height="6" rx="1.5" fill="#ffffff" />
    <rect x="42" y="38" width="7" height="6" rx="1.5" fill="#ffffff" />
    <rect x="54" y="38" width="7" height="6" rx="1.5" fill="#ffffff" />

    <rect x="30" y="48" width="7" height="6" rx="1.5" fill="#ffffff" />
    <rect x="42" y="48" width="7" height="6" rx="1.5" fill="#ffffff" />
    <rect x="54" y="48" width="7" height="6" rx="1.5" fill="#ffffff" opacity="0.6" />

    <rect x="30" y="58" width="7" height="6" rx="1.5" fill="#ffffff" />
    <rect x="42" y="58" width="7" height="6" rx="1.5" fill="#ffffff" opacity="0.6" />

    {/* Clock Badge (Bottom Right Overlay) */}
    <circle cx="68" cy="68" r="16" fill="#ffffff" stroke="#1d4ed8" strokeWidth="4" />
    <circle cx="68" cy="68" r="2.5" fill="#1d4ed8" />
    <line x1="68" y1="68" x2="68" y2="58" stroke="#1d4ed8" strokeWidth="3" strokeLinecap="round" />
    <line x1="68" y1="68" x2="76" y2="68" stroke="#1d4ed8" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

// 9. Latest Event Icon (Dark Slate Document with Clock Badge)
export const LatestEventIcon: React.FC<{ className?: string }> = ({ className = 'w-12 h-12' }) => (
  <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <defs>
      <linearGradient id="doc-slate" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#334155" />
        <stop offset="100%" stopColor="#1e293b" />
      </linearGradient>
    </defs>

    {/* Document Body */}
    <rect x="24" y="20" width="50" height="58" rx="8" fill="url(#doc-slate)" />

    {/* Document Header Text Line */}
    <rect x="32" y="30" width="34" height="4" rx="2" fill="#f8fafc" />

    {/* Horizontal Content Lines */}
    <rect x="32" y="40" width="34" height="3" rx="1.5" fill="#94a3b8" />
    <rect x="32" y="48" width="28" height="3" rx="1.5" fill="#94a3b8" />
    <rect x="32" y="56" width="20" height="3" rx="1.5" fill="#94a3b8" />

    {/* Clock Badge (Bottom Right Overlay) */}
    <circle cx="68" cy="68" r="15" fill="#1e293b" stroke="#ffffff" strokeWidth="3" />
    <circle cx="68" cy="68" r="2" fill="#ffffff" />
    <line x1="68" y1="68" x2="68" y2="59" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" />
    <line x1="68" y1="68" x2="75" y2="68" stroke="#ffffff" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
);

// 10. BCSS Wallet Icon (Card style wallet)
export const WalletCardIcon: React.FC<{ className?: string }> = ({ className = 'w-8 h-8' }) => (
  <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg" className={className}>
    <rect x="6" y="12" width="36" height="26" rx="4" fill="#ffffff" stroke="#334155" strokeWidth="3" />
    <path d="M6 18H42" stroke="#334155" strokeWidth="2" />
    {/* Wallet Flap */}
    <path
      d="M30 20H42V30H30C27.7909 30 26 28.2091 26 26C26 23.7909 27.7909 20 30 20Z"
      fill="#f43f5e"
      stroke="#334155"
      strokeWidth="2"
    />
    <circle cx="34" cy="25" r="2" fill="#ffffff" />
  </svg>
);
