export type Language = 'en' | 'hi';

export interface Translations {
  // App & Header
  appTitle: string;
  appSubtitle: string;
  online: string;
  syncing: string;
  buzzerAudio: string;
  buzzerEnabled: string;
  buzzerTest: string;
  signOut: string;
  operator: string;
  language: string;
  switchLang: string;

  // Nav Dock
  navHome: string;
  navSchedules: string;
  navActivity: string;
  navAdmin: string;
  dockStart: string;
  dockStop: string;
  dockRunning: string;
  dockPump: string;

  // Common Actions & Badges
  backToHome: string;
  save: string;
  saving: string;
  savedSuccessfully: string;
  cancel: string;
  delete: string;
  confirm: string;
  confirmDelete: string;
  refresh: string;
  active: string;
  select: string;
  unitsOnline: string;
  realLocalTime: string;
  targetTime: string;

  // Home Dashboard
  stationStatus: string;
  selectActiveMotor: string;
  smartWaterManagement: string;
  monitorControlHeader: string;
  heroSub: string;
  systemOnline: string;
  allParametersNormal: string;
  realtimeMonitoring: string;
  safeReliableOperation: string;
  bcssAccount: string;
  balance: string;
  pumpActive: string;
  scheduledOperation: string;
  motorWillStopIn: string;
  extend15m: string;
  stopNow: string;
  current: string;
  voltage: string;
  power: string;

  // 9 Function Grid Cards
  cardSelectMotor: string;
  cardInterlocks: string;
  cardTankLevel: string;
  cardSumpLevel: string;
  cardFlowRate: string;
  cardWaterQuality: string;
  cardElectricalLoad: string;
  cardSchedules: string;
  cardLatestEvent: string;

  // Start Motor Modal
  startPumpWithTimer: string;
  autoCutoffScheduleSub: string;
  safetyOk: string;
  runtimeDuration: string;
  customCutoffTimer: string;
  scheduledAutoCutoff: string;
  autoCutoffExplainer: string;
  starting: string;
  startBtn: string;
  preset15m: string;
  preset30m: string;
  preset45m: string;
  preset60m: string;
  preset90m: string;
  presetCustom: string;
  presetSubFast: string;
  presetSubStandard: string;
  presetSubTopup: string;
  presetSubFull: string;
  presetSubHeavy: string;
  presetSubUser: string;

  // Tank Level Screen
  overheadTankTitle: string;
  overheadTankSubtitle: string;
  tankFull: string;
  tankFilling: string;
  waterHeadHeight: string;
  tankCutoffThreshold: string;
  tankFullRuleTitle: string;
  tankFullRuleDesc: string;
  saveTankThreshold: string;
  earlyStop: string;
  maxFull: string;

  // Sump Level Screen
  sumpTitle: string;
  sumpSubtitle: string;
  dryRunSafe: string;
  dryRunWarning: string;
  effectiveReserve: string;
  sumpCutoffThreshold: string;
  sumpRuleTitle: string;
  sumpRuleDesc: string;
  saveSumpThreshold: string;
  minSafe: string;
  highReserve: string;

  // Flow Rate Screen
  flowTitle: string;
  flowSubtitle: string;
  flowActive: string;
  flowStatic: string;
  currentDischarge: string;
  flowVolumePerHour: string;
  pipeVelocity: string;
  dailyDischarged: string;
  flowSensorStatus: string;

  // Water Quality Screen
  waterQualityTitle: string;
  waterQualitySubtitle: string;
  potableSafe: string;
  turbidityWarning: string;
  turbidityScore: string;
  phBalance: string;
  turbidityThresholdTitle: string;
  saveQualityThreshold: string;

  // Electrical Load Screen
  electricalTitle: string;
  electricalSubtitle: string;
  operatingNormal: string;
  loadWarning: string;
  motorCurrent: string;
  lineVoltage: string;
  activePowerKw: string;
  powerFactor: string;
  frequency: string;

  // Interlocks Screen
  interlocksTitle: string;
  interlocksSubtitle: string;
  allInterlocksHealthy: string;
  interlockTripped: string;
  systemProtectionActive: string;
  tankLevelCheck: string;
  sumpDryRunCheck: string;
  waterClarityCheck: string;
  overloadCheck: string;
  voltageCheck: string;

  // Schedules Screen
  schedulesTitle: string;
  schedulesSubtitle: string;
  addScheduleBtn: string;
  activeTimersCount: string;
  dailyScheduleNotice: string;
  pause: string;
  enable: string;
  deleteScheduleTitle: string;
  deleteScheduleSub: string;

  // Latest Events Screen
  latestEventsTitle: string;
  latestEventsSubtitle: string;
  allMotors: string;
  allTypes: string;
  totalRunTime: string;
  scheduledRuns: string;
  manualRuns: string;
  runtimeLogs: string;
  liveSessions: string;
  rawEvents: string;
  noEventsFound: string;

  // BCSS Account Screen
  bcssTitle: string;
  bcssSubtitle: string;
  walletBalance: string;
  activeTier: string;
  rechargeBtn: string;
  adminPortalBtn: string;
}

export const translations: Record<Language, Translations> = {
  en: {
    // App & Header
    appTitle: 'HydraControl',
    appSubtitle: 'Commercial IoT Automation',
    online: 'ONLINE',
    syncing: 'SYNCING',
    buzzerAudio: 'Buzzer Audio Alerts',
    buzzerEnabled: 'ENABLED',
    buzzerTest: 'TEST SOUND',
    signOut: 'Sign Out',
    operator: 'Operator',
    language: 'Language',
    switchLang: 'हिन्दी',

    // Nav Dock
    navHome: 'Home',
    navSchedules: 'Schedules',
    navActivity: 'Activity',
    navAdmin: 'Admin',
    dockStart: 'START',
    dockStop: 'STOP',
    dockRunning: 'RUNNING',
    dockPump: 'PUMP',

    // Common Actions & Badges
    backToHome: 'Back to Home',
    save: 'Save',
    saving: 'Saving...',
    savedSuccessfully: 'Saved Successfully!',
    cancel: 'Cancel',
    delete: 'Delete',
    confirm: 'Confirm',
    confirmDelete: 'Confirm Delete',
    refresh: 'Refresh',
    active: '✓ ACTIVE',
    select: 'SELECT',
    unitsOnline: 'Units Online',
    realLocalTime: 'Real Local Time',
    targetTime: 'Target Time',

    // Home Dashboard
    stationStatus: 'Station Status',
    selectActiveMotor: 'SELECT ACTIVE MOTOR',
    smartWaterManagement: 'SMART WATER MANAGEMENT',
    monitorControlHeader: 'Monitor & Control Your Pump Station',
    heroSub: 'Reliable • Real-time • Efficient',
    systemOnline: 'System Online',
    allParametersNormal: 'All Parameters Normal',
    realtimeMonitoring: 'Real-time Monitoring',
    safeReliableOperation: 'Safe & Reliable Operation',
    bcssAccount: 'BCSS Account',
    balance: 'Balance',
    pumpActive: 'PUMP ACTIVE',
    scheduledOperation: 'Scheduled Operation',
    motorWillStopIn: '⚠️ Motor Will Stop in',
    extend15m: 'CONTINUE (+15 MIN)',
    stopNow: 'STOP NOW',
    current: 'Current',
    voltage: 'Voltage',
    power: 'Power',

    // 9 Function Grid Cards
    cardSelectMotor: 'Select Active Motor',
    cardInterlocks: 'Interlocks',
    cardTankLevel: 'Tank Level',
    cardSumpLevel: 'Sump Level',
    cardFlowRate: 'Flow Rate',
    cardWaterQuality: 'Water Quality',
    cardElectricalLoad: 'Electrical Load',
    cardSchedules: 'Schedules',
    cardLatestEvent: 'Latest Event',

    // Start Motor Modal
    startPumpWithTimer: 'START PUMP WITH TIMER',
    autoCutoffScheduleSub: 'Auto-cutoff countdown & safety interlocks',
    safetyOk: 'Safety OK',
    runtimeDuration: 'Runtime Duration',
    customCutoffTimer: 'Custom Cutoff Timer',
    scheduledAutoCutoff: 'Scheduled Auto-Cutoff',
    autoCutoffExplainer: 'Pump will run for specified time then shut off automatically.',
    starting: 'STARTING...',
    startBtn: 'START',
    preset15m: '15 Min',
    preset30m: '30 Min',
    preset45m: '45 Min',
    preset60m: '60 Min',
    preset90m: '90 Min',
    presetCustom: 'Custom',
    presetSubFast: 'Quick cycle',
    presetSubStandard: 'Standard run',
    presetSubTopup: 'Tank top-up',
    presetSubFull: 'Full cycle (1h)',
    presetSubHeavy: 'Deep irrigation',
    presetSubUser: 'Custom runtime',

    // Tank Level Screen
    overheadTankTitle: 'Overhead Storage Tank',
    overheadTankSubtitle: 'Real-time water depth and level telemetry',
    tankFull: 'TANK FULL',
    tankFilling: 'FILLING / NORMAL',
    waterHeadHeight: 'Water Head Height',
    tankCutoffThreshold: 'Overhead Tank Full Auto-Cutoff Threshold',
    tankFullRuleTitle: 'Auto-Stop on Tank Full Rule',
    tankFullRuleDesc: 'Enforce hardware cutoff when level reaches threshold',
    saveTankThreshold: 'Save Tank Threshold',
    earlyStop: '70% (Early Stop)',
    maxFull: '100% (Maximum Full)',

    // Sump Level Screen
    sumpTitle: 'Ground Water Sump',
    sumpSubtitle: 'Underground reservoir level & dry run protection',
    dryRunSafe: 'RESERVE HEALTHY',
    dryRunWarning: 'DRY RUN RISK',
    effectiveReserve: 'Effective Reserve Depth',
    sumpCutoffThreshold: 'Sump Dry-Run Protection Cutoff Threshold',
    sumpRuleTitle: 'Auto-Trip on Low Water Rule',
    sumpRuleDesc: 'Immediately trip pump if sump level drops below safety limit',
    saveSumpThreshold: 'Save Sump Threshold',
    minSafe: '15% (Minimum Safe)',
    highReserve: '50% (High Reserve)',

    // Flow Rate Screen
    flowTitle: 'Flow Rate & Discharge',
    flowSubtitle: 'Electromagnetic flow meter telemetry and line pressure',
    flowActive: 'FLOWING ACTIVE',
    flowStatic: 'STATIC / NO FLOW',
    currentDischarge: 'Current Discharge',
    flowVolumePerHour: 'Hourly Volume',
    pipeVelocity: 'Estimated Pipe Velocity',
    dailyDischarged: 'Total Run Volume Today',
    flowSensorStatus: 'Turbine Pulse Sensor Active',

    // Water Quality Screen
    waterQualityTitle: 'Water Potability & Quality',
    waterQualitySubtitle: 'Turbidity, dissolved solids, and pH safety indicators',
    potableSafe: 'POTABLE / SAFE',
    turbidityWarning: 'TURBIDITY HIGH',
    turbidityScore: 'Water Turbidity',
    phBalance: 'pH Level',
    turbidityThresholdTitle: 'Max Permissible Turbidity Threshold',
    saveQualityThreshold: 'Save Quality Threshold',

    // Electrical Load Screen
    electricalTitle: 'Electrical Load & Phase Health',
    electricalSubtitle: 'Real-time motor current, line voltage, and active power',
    operatingNormal: 'ELECTRICAL OK',
    loadWarning: 'OVERCURRENT RISK',
    motorCurrent: 'Motor Current Draw',
    lineVoltage: 'Supply Voltage',
    activePowerKw: 'Active Power Draw',
    powerFactor: 'Power Factor',
    frequency: 'Grid Frequency',

    // Interlocks Screen
    interlocksTitle: 'Safety Interlocks Matrix',
    interlocksSubtitle: 'Five-point hardware interlocking protection suite',
    allInterlocksHealthy: 'All 5 Interlocks Healthy',
    interlockTripped: 'Interlock Warning / Tripped',
    systemProtectionActive: 'System Protection Active',
    tankLevelCheck: 'Tank Full Interlock',
    sumpDryRunCheck: 'Sump Dry-Run Interlock',
    waterClarityCheck: 'Water Quality Turbidity Interlock',
    overloadCheck: 'Motor Overcurrent Interlock',
    voltageCheck: 'Phase & Voltage Stability Interlock',

    // Schedules Screen
    schedulesTitle: 'Automated Timer Schedules',
    schedulesSubtitle: 'Pre-programmed automated motor routines',
    addScheduleBtn: 'Add Schedule',
    activeTimersCount: 'Configured Daily Schedules',
    dailyScheduleNotice: 'Schedules execute automatically every day at designated times.',
    pause: 'Pause',
    enable: 'Enable',
    deleteScheduleTitle: 'Delete Schedule?',
    deleteScheduleSub: 'This routine will stop executing.',

    // Latest Events Screen
    latestEventsTitle: 'Motor Activity & Audit Log',
    latestEventsSubtitle: 'Chronological telemetry and run session audit history',
    allMotors: 'All Motors',
    allTypes: 'All Types',
    totalRunTime: 'Total Run Time',
    scheduledRuns: 'Scheduled',
    manualRuns: 'Manual',
    runtimeLogs: 'Run Sessions',
    liveSessions: 'Sessions',
    rawEvents: 'Events',
    noEventsFound: 'No events matching filter.',

    // BCSS Account Screen
    bcssTitle: 'BCSS Account & Organization',
    bcssSubtitle: 'Commercial IoT subscription and station management',
    walletBalance: 'Current Wallet Balance',
    activeTier: 'Commercial Tier Active',
    rechargeBtn: 'Recharge Balance',
    adminPortalBtn: 'Open Organization Admin Panel',
  },

  hi: {
    // App & Header
    appTitle: 'हाइड्राकंट्रोल',
    appSubtitle: 'कमर्शियल IoT मोटर ऑटोमेशन',
    online: 'ऑनलाइन',
    syncing: 'सिंक हो रहा है',
    buzzerAudio: 'बजर ध्वनि अलर्ट',
    buzzerEnabled: 'चालू है',
    buzzerTest: 'आवाज़ जांचें',
    signOut: 'लॉग आउट',
    operator: 'ऑपरेटर',
    language: 'भाषा',
    switchLang: 'English',

    // Nav Dock
    navHome: 'होम',
    navSchedules: 'शेड्यूल',
    navActivity: 'गतिविधि',
    navAdmin: 'एडमिन',
    dockStart: 'शुरू करें',
    dockStop: 'बंद करें',
    dockRunning: 'चालू है',
    dockPump: 'मोटर पंप',

    // Common Actions & Badges
    backToHome: 'मुख्य पृष्ठ पर वापस',
    save: 'सहेजें',
    saving: 'सहेजा जा रहा है...',
    savedSuccessfully: 'सफलतापूर्वक सहेजा गया!',
    cancel: 'रद्द करें',
    delete: 'हटाएं',
    confirm: 'पुष्टि करें',
    confirmDelete: 'हटाने की पुष्टि करें',
    refresh: 'रीफ़्रेश करें',
    active: '✓ सक्रिय',
    select: 'चुनें',
    unitsOnline: 'मोटर चालू हैं',
    realLocalTime: 'स्थानीय समय',
    targetTime: 'लक्षित समय',

    // Home Dashboard
    stationStatus: 'पंप स्टेशन स्थिति',
    selectActiveMotor: 'सक्रिय मोटर चुनें',
    smartWaterManagement: 'स्मार्ट जल प्रबंधन प्रणाली',
    monitorControlHeader: 'पंप स्टेशन की लाइव निगरानी व नियंत्रण',
    heroSub: 'विश्वसनीय • रीयल-टाइम • ऊर्जा-दक्ष',
    systemOnline: 'सिस्टम ऑनलाइन है',
    allParametersNormal: 'सभी पैरामीटर सामान्य हैं',
    realtimeMonitoring: 'रीयल-टाइम निगरानी चालू',
    safeReliableOperation: 'सुरक्षित एवं विश्वसनीय संचालन',
    bcssAccount: 'BCSS खाता',
    balance: 'शेष राशि',
    pumpActive: 'पंप सक्रिय है',
    scheduledOperation: 'निर्धारित संचालन',
    motorWillStopIn: '⚠️ मोटर बंद होने में शेष समय',
    extend15m: 'समय बढ़ाएं (+15 मिनट)',
    stopNow: 'अभी बंद करें',
    current: 'करंट (एम्पीयर)',
    voltage: 'वोल्टेज (वोल्ट)',
    power: 'पावर (kW)',

    // 9 Function Grid Cards
    cardSelectMotor: 'सक्रिय मोटर चुनें',
    cardInterlocks: 'सुरक्षा इंटरलॉक्स',
    cardTankLevel: 'टंकी जल स्तर',
    cardSumpLevel: 'हौद / सम्प स्तर',
    cardFlowRate: 'जल प्रवाह दर',
    cardWaterQuality: 'पानी की गुणवत्ता',
    cardElectricalLoad: 'बिजली लोड',
    cardSchedules: 'दैनिक समय सारणी',
    cardLatestEvent: 'हालिया इतिहास',

    // Start Motor Modal
    startPumpWithTimer: 'टाइमर के साथ मोटर चालू करें',
    autoCutoffScheduleSub: 'ऑटो कट-ऑफ उलटी गिनती और सुरक्षा जांच',
    safetyOk: 'सुरक्षा जांच सफल',
    runtimeDuration: 'चलने की अवधि चुनें',
    customCutoffTimer: 'कस्टम कट-ऑफ टाइमर',
    scheduledAutoCutoff: 'निर्धारित ऑटो कट-ऑफ समय',
    autoCutoffExplainer: 'मोटर चुने गए समय तक चलेगी और स्वतः बंद हो जाएगी।',
    starting: 'शुरू हो रहा है...',
    startBtn: 'शुरू करें',
    preset15m: '15 मिनट',
    preset30m: '30 मिनट',
    preset45m: '45 मिनट',
    preset60m: '60 मिनट (1 घंटा)',
    preset90m: '90 मिनट (1.5 घंटा)',
    presetCustom: 'कस्टम',
    presetSubFast: 'तेज़ चक्र',
    presetSubStandard: 'सामान्य संचालन',
    presetSubTopup: 'टंकी भरने हेतु',
    presetSubFull: 'पूरा चक्र (1 घंटा)',
    presetSubHeavy: 'गहरी सिंचाई / भराव',
    presetSubUser: 'अपनी इच्छानुसार समय',

    // Tank Level Screen
    overheadTankTitle: 'ऊपरी पानी की टंकी',
    overheadTankSubtitle: 'लाइव जल स्तर एवं गहराई टेलीमेट्री',
    tankFull: 'टंकी भर गई है',
    tankFilling: 'पानी भर रहा है / सामान्य',
    waterHeadHeight: 'वाटर हेड ऊंचाई',
    tankCutoffThreshold: 'टंकी भरने पर ऑटो कट-ऑफ सीमा',
    tankFullRuleTitle: 'टंकी भरने पर स्वतः बंद करने का नियम',
    tankFullRuleDesc: 'जब स्तर इस सीमा पर पहुंचे तो मोटर अपने आप बंद कर दें',
    saveTankThreshold: 'टंकी सीमा सहेजें',
    earlyStop: '70% (शीघ्र बंद)',
    maxFull: '100% (पूरी भरी टंकी)',

    // Sump Level Screen
    sumpTitle: 'भूमिगत जल हौद (सम्प)',
    sumpSubtitle: 'निचले जलाशय का स्तर एवं ड्राय-रन सुरक्षा',
    dryRunSafe: 'जल भंडार सुरक्षित है',
    dryRunWarning: 'ड्राय-रन का खतरा (पानी कम)',
    effectiveReserve: 'प्रभावी जल गहराई',
    sumpCutoffThreshold: 'सम्प ड्राय-रन सुरक्षा कट-ऑफ सीमा',
    sumpRuleTitle: 'पानी कम होने पर मोटर ट्रिप नियम',
    sumpRuleDesc: 'सम्प का स्तर सीमा से नीचे जाते ही मोटर तुरंत बंद हो जाएगी',
    saveSumpThreshold: 'सम्प सीमा सहेजें',
    minSafe: '15% (न्यूनतम सुरक्षित)',
    highReserve: '50% (अधिक भंडार)',

    // Flow Rate Screen
    flowTitle: 'जल प्रवाह दर एवं डिस्चार्ज',
    flowSubtitle: 'इलेक्ट्रोमैग्नेटिक फ्लो मीटर टेलीमेट्री एवं पाइप प्रेशर',
    flowActive: 'जल प्रवाह चालू है',
    flowStatic: 'स्थिर / कोई प्रवाह नहीं',
    currentDischarge: 'वर्तमान डिस्चार्ज',
    flowVolumePerHour: 'प्रति घंटा आयतन',
    pipeVelocity: 'अनुमानित पाइप प्रवाह गति',
    dailyDischarged: 'आज का कुल डिस्चार्ज',
    flowSensorStatus: 'टर्बाइन पल्स सेंसर सक्रिय',

    // Water Quality Screen
    waterQualityTitle: 'पानी की शुद्धता एवं गुणवत्ता',
    waterQualitySubtitle: 'गंदलापन (टर्बिडिटी), घुलित ठोस और पीएच सुरक्षा स्तर',
    potableSafe: 'पीने योग्य / पूर्ण सुरक्षित',
    turbidityWarning: 'गंदलापन अधिक है (खतरा)',
    turbidityScore: 'गंदलापन स्तर (Turbidity)',
    phBalance: 'पीएच मान (pH)',
    turbidityThresholdTitle: 'अधिकतम स्वीकार्य गंदलापन सीमा',
    saveQualityThreshold: 'गुणवत्ता सीमा सहेजें',

    // Electrical Load Screen
    electricalTitle: 'बिजली लोड एवं मोटर स्वास्थ्य',
    electricalSubtitle: 'मोटर करंट, सप्लाई वोल्टेज और सक्रिय पावर की निगरानी',
    operatingNormal: 'विद्युत स्थिति सामान्य',
    loadWarning: 'ओवरकरंट का खतरा',
    motorCurrent: 'मोटर करंट (Amps)',
    lineVoltage: 'सप्लाई वोल्टेज (Volts)',
    activePowerKw: 'सक्रिय विद्युत खपत (kW)',
    powerFactor: 'पावर फैक्टर',
    frequency: 'ग्रिड फ्रीक्वेंसी',

    // Interlocks Screen
    interlocksTitle: 'सुरक्षा इंटरलॉक मैट्रिक्स',
    interlocksSubtitle: 'पंच-बिंदु हार्डवेयर सुरक्षा एवं मोटर प्रोटेक्शन',
    allInterlocksHealthy: 'सभी 5 सुरक्षा इंटरलॉक सुरक्षित हैं',
    interlockTripped: 'इंटरलॉक चेतावनी / सुरक्षा ट्रिप',
    systemProtectionActive: 'सिस्टम सुरक्षा सक्रिय है',
    tankLevelCheck: 'टंकी भराव सुरक्षा इंटरलॉक',
    sumpDryRunCheck: 'सम्प ड्राय-रन सुरक्षा इंटरलॉक',
    waterClarityCheck: 'जल गुणवत्ता गंदलापन इंटरलॉक',
    overloadCheck: 'मोटर ओवरकरंट सुरक्षा इंटरलॉक',
    voltageCheck: 'फेज एवं वोल्टेज स्थिरता इंटरलॉक',

    // Schedules Screen
    schedulesTitle: 'स्वचालित दैनिक समय सारणी',
    schedulesSubtitle: 'पूर्व-निर्धारित स्वचालित मोटर संचालन रूटीन',
    addScheduleBtn: 'नया शेड्यूल जोड़ें',
    activeTimersCount: 'सक्रिय दैनिक टाइमर',
    dailyScheduleNotice: 'यह शेड्यूल प्रतिदिन निर्धारित समय पर स्वचालित रूप से चलेंगे।',
    pause: 'रोकें',
    enable: 'चालू करें',
    deleteScheduleTitle: 'शेड्यूल हटाएं?',
    deleteScheduleSub: 'यह स्वचालित रूटीन बंद हो जाएगा।',

    // Latest Events Screen
    latestEventsTitle: 'मोटर संचालन इतिहास व ऑडिट लॉग',
    latestEventsSubtitle: 'समयबद्ध टेलीमेट्री एवं मोटर चलने का संपूर्ण रिकॉर्ड',
    allMotors: 'सभी मोटर्स',
    allTypes: 'सभी प्रकार',
    totalRunTime: 'कुल चलने का समय',
    scheduledRuns: 'शेड्यूल अनुसार',
    manualRuns: 'मैन्युअल शुरुआत',
    runtimeLogs: 'संचालन सत्र (Sessions)',
    liveSessions: 'सत्र',
    rawEvents: 'इवेंट्स',
    noEventsFound: 'कोई इतिहास रिकॉर्ड नहीं मिला।',

    // BCSS Account Screen
    bcssTitle: 'BCSS खाता एवं संस्था',
    bcssSubtitle: 'कमर्शियल IoT सब्सक्रिप्शन एवं स्टेशन प्रबंधन',
    walletBalance: 'वर्तमान वॉलेट शेष राशि',
    activeTier: 'कमर्शियल टियर सक्रिय',
    rechargeBtn: 'खाता रिचार्ज करें',
    adminPortalBtn: 'संस्था एडमिन पैनल खोलें',
  },
};
