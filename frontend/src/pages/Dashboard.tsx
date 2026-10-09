import React, { useState, useEffect, useMemo } from 'react';
import {
  Users,
  CreditCard,
  Building2,
  Shield,
  UserPlus,
  Trash2,
  CheckCircle2,
  XCircle,
  Sparkles,
  Search,
  Filter,
  RefreshCw,
  Crown,
  ChevronRight,
  Mail,
  Lock,
  User as UserIcon,
  Check,
  AlertTriangle,
  Loader2,
  MapPin,
  ShieldCheck,
  Zap,
} from 'lucide-react';
import {
  User,
  UserRole,
  UserAdminCreate,
  SubscriptionPlanInfo,
  SubscriptionResponse,
  Site,
  WsServerEvent,
} from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

interface DashboardProps {
  latestWsEvent?: WsServerEvent | null;
}

type AdminTab = 'USERS' | 'SUBSCRIPTION' | 'ORGANIZATION' | 'SECURITY';

const AVAILABLE_ROLES: { role: UserRole; label: string; desc: string; badgeColor: string }[] = [
  {
    role: 'STATION_OPERATOR',
    label: 'Station Operator',
    desc: 'Full day-to-day operational control: motor start/stop, safety cutoff thresholds, and schedules.',
    badgeColor: 'bg-teal-500/10 text-teal-400 border-teal-500/30',
  },
  {
    role: 'SITE_MANAGER',
    label: 'Site Manager',
    desc: 'Supervises physical sites, field controllers, sensor safety interlocks, and telemetry diagnostics.',
    badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  },
  {
    role: 'ORGANIZATION_ADMIN',
    label: 'Organization Admin',
    desc: 'Business management: manage team user accounts, assign roles, and configure subscription plans.',
    badgeColor: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  },
  {
    role: 'TECHNICIAN',
    label: 'Field Technician',
    desc: 'Hardware commissioning, sensor calibration, MQTT gateway configuration, and maintenance logs.',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  {
    role: 'VIEWER',
    label: 'Read-Only Viewer',
    desc: 'Monitor real-time tank levels and operational history logs without command execution permissions.',
    badgeColor: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  },
];

export const Dashboard: React.FC<DashboardProps> = ({ latestWsEvent }) => {
  const { user: currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>('USERS');

  // Loading and feedback states
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Business Data States
  const [users, setUsers] = useState<User[]>([]);
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlanInfo[]>([]);
  const [sites, setSites] = useState<Site[]>([]);

  // User Filter & Search States
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');

  // Modals & Action States
  const [isAddUserModalOpen, setIsAddUserModalOpen] = useState<boolean>(false);
  const [isSubmittingUser, setIsSubmittingUser] = useState<boolean>(false);
  const [newUserName, setNewUserName] = useState<string>('');
  const [newUserEmail, setNewUserEmail] = useState<string>('');
  const [newUserPassword, setNewUserPassword] = useState<string>('');
  const [newUserRole, setNewRole] = useState<UserRole>('STATION_OPERATOR');

  const [userToEditRole, setUserToEditRole] = useState<User | null>(null);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [isDeletingUser, setIsDeletingUser] = useState<boolean>(false);

  const [planToSwitch, setPlanToSwitch] = useState<SubscriptionPlanInfo | null>(null);
  const [isUpdatingPlan, setIsUpdatingPlan] = useState<boolean>(false);

  // Initial Data Fetch
  const loadAdminData = async (showRefreshIndicator = false) => {
    if (showRefreshIndicator) setIsRefreshing(true);
    try {
      setErrorMessage(null);
      const [usersRes, subRes, plansRes, sitesRes] = await Promise.allSettled([
        api.getUsers(),
        api.getCurrentSubscription(),
        api.getSubscriptionPlans(),
        api.getSites(),
      ]);

      if (usersRes.status === 'fulfilled') {
        setUsers(usersRes.value);
      }
      if (subRes.status === 'fulfilled') {
        setSubscription(subRes.value);
      }
      if (plansRes.status === 'fulfilled') {
        setPlans(plansRes.value);
      }
      if (sitesRes.status === 'fulfilled') {
        setSites(sitesRes.value);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load business administration data');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadAdminData();
  }, []);

  // Sync if WebSocket user/billing/motor events arrive
  useEffect(() => {
    if (latestWsEvent) {
      const e = latestWsEvent.event;
      if (e === 'NOTIFICATION_RECEIVED' || e === 'MOTOR_STATE' || e === 'SAFETY_ALERT') {
        loadAdminData();
      }
    }
  }, [latestWsEvent]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // Filtered Users list
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const matchesSearch =
        u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        u.email.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesRole = roleFilter === 'ALL' || u.role === roleFilter;
      return matchesSearch && matchesRole;
    });
  }, [users, searchQuery, roleFilter]);

  // Handle Add New User
  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserName.trim() || !newUserEmail.trim() || !newUserPassword.trim()) {
      showToast('Please provide name, email, and password.');
      return;
    }

    setIsSubmittingUser(true);
    try {
      const payload: UserAdminCreate = {
        name: newUserName.trim(),
        email: newUserEmail.trim(),
        password: newUserPassword,
        role: newUserRole,
        is_active: true,
      };
      const created = await api.createUser(payload);
      setUsers((prev) => [created, ...prev]);
      showToast(`✓ User account created for ${created.name} (${created.role})`);
      setIsAddUserModalOpen(false);
      setNewUserName('');
      setNewUserEmail('');
      setNewUserPassword('');
      setNewRole('STATION_OPERATOR');
      loadAdminData();
    } catch (err: any) {
      showToast(err.message || 'Failed to create user account');
    } finally {
      setIsSubmittingUser(false);
    }
  };

  // Handle User Status Toggle
  const handleToggleUserStatus = async (targetUser: User) => {
    try {
      const updated = await api.updateUser(targetUser.id, {
        is_active: !targetUser.is_active,
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      showToast(`User status set to ${updated.is_active ? 'ACTIVE' : 'INACTIVE'}`);
    } catch (err: any) {
      showToast(err.message || 'Failed to update user status');
    }
  };

  // Handle User Role Change
  const handleUpdateRole = async (targetUser: User, newRoleToSet: UserRole) => {
    try {
      const updated = await api.updateUser(targetUser.id, {
        role: newRoleToSet,
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      showToast(`Role for ${updated.name} updated to ${updated.role}`);
      setUserToEditRole(null);
    } catch (err: any) {
      showToast(err.message || 'Failed to update user role');
    }
  };

  // Handle User Deletion
  const handleDeleteUser = async () => {
    if (!userToDelete) return;
    setIsDeletingUser(true);
    try {
      await api.deleteUser(userToDelete.id);
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id));
      showToast(`User ${userToDelete.name} has been deleted`);
      setUserToDelete(null);
      loadAdminData();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete user');
    } finally {
      setIsDeletingUser(false);
    }
  };

  // Handle Plan Tier Switch
  const handleConfirmPlanSwitch = async () => {
    if (!planToSwitch) return;
    setIsUpdatingPlan(true);
    try {
      const updated = await api.updateSubscriptionPlan({
        tier: planToSwitch.tier,
      });
      setSubscription(updated);
      showToast(`✓ Upgraded subscription to ${updated.tier} Tier!`);
      setPlanToSwitch(null);
      loadAdminData();
    } catch (err: any) {
      showToast(err.message || 'Failed to update subscription tier');
    } finally {
      setIsUpdatingPlan(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-[70vh] flex flex-col items-center justify-center space-y-4 font-['Plus_Jakarta_Sans',sans-serif]">
        <Loader2 className="w-10 h-10 animate-spin text-cyan-400" />
        <p className="text-sm font-semibold text-slate-400">Loading Business Administration Suite...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-['Plus_Jakarta_Sans',sans-serif] pb-16">
      {/* Toast Banner */}
      {toastMessage && (
        <div className="fixed top-20 right-6 z-50 animate-bounce-in">
          <div className="px-4 py-3 rounded-2xl bg-slate-900/95 border border-cyan-500/40 text-cyan-200 text-xs font-bold shadow-2xl shadow-cyan-500/20 backdrop-blur-md flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span>{toastMessage}</span>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
          <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-bold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400" />
            <span>{errorMessage}</span>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 space-y-8">
        {/* ========================================================================= */}
        {/* 1. EXECUTIVE HERO HEADER */}
        {/* ========================================================================= */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 rounded-3xl bg-gradient-to-r from-slate-900 via-slate-900/80 to-slate-950 border border-slate-800 shadow-2xl relative overflow-hidden">
          <div className="absolute -top-24 -right-24 w-72 h-72 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

          <div className="space-y-1.5 z-10">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-xl bg-purple-500/20 border border-purple-500/40 text-purple-300 text-[10px] font-black uppercase tracking-wider flex items-center gap-1">
                <Crown className="w-3.5 h-3.5 text-purple-400" />
                <span>Executive Admin Console</span>
              </span>
              {subscription && (
                <span className="px-2.5 py-1 rounded-xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-300 text-[10px] font-black uppercase">
                  ● {subscription.tier} ACTIVE
                </span>
              )}
            </div>

            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              Business &amp; Team Management
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 font-medium">
              Manage organization members, assign operational roles, control seat limits, and configure commercial subscription quotas.
            </p>
          </div>

          <div className="flex items-center gap-3 z-10 flex-wrap">
            <button
              type="button"
              onClick={() => loadAdminData(true)}
              disabled={isRefreshing}
              className="px-3.5 py-2.5 rounded-2xl bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-bold border border-slate-700/80 flex items-center gap-2 transition-all cursor-pointer shadow-sm disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-cyan-400' : ''}`} />
              <span>{isRefreshing ? 'Refreshing...' : 'Refresh'}</span>
            </button>

            <button
              type="button"
              onClick={() => setIsAddUserModalOpen(true)}
              className="px-4 py-2.5 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-black shadow-lg shadow-purple-600/25 flex items-center gap-2 transition-all cursor-pointer transform active:scale-95"
            >
              <UserPlus className="w-4 h-4" />
              <span>+ Add Team Member</span>
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 2. BUSINESS KPI STAT CARDS */}
        {/* ========================================================================= */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Card 1: Active Seats */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider">
                Team Seats Quota
              </span>
              <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400">
                <Users className="w-4 h-4" />
              </div>
            </div>
            <div>
              <div className="text-2xl font-black text-white">
                {users.length}{' '}
                <span className="text-sm font-bold text-slate-500">
                  / {subscription?.max_users || '∞'} Seats
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                {users.filter((u) => u.is_active).length} Active Members
              </div>
            </div>
            {/* Progress bar */}
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.round((users.length / (subscription?.max_users || 1)) * 100))}%`,
                }}
              />
            </div>
          </div>

          {/* Card 2: Active Plan Tier */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider">
                Subscription Tier
              </span>
              <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
                <CreditCard className="w-4 h-4" />
              </div>
            </div>
            <div>
              <div className="text-2xl font-black text-cyan-300">
                {subscription?.tier || 'STARTER'}
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Renews: {subscription?.renewal_date || 'Annual Auto-Renew'}
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('SUBSCRIPTION')}
              className="text-[11px] font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors cursor-pointer"
            >
              <span>Manage Plan Quotas</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          {/* Card 3: Motor Limits */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider">
                Motor Deployments
              </span>
              <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400">
                <Zap className="w-4 h-4" />
              </div>
            </div>
            <div>
              <div className="text-2xl font-black text-white">
                {subscription?.current_motors || 0}{' '}
                <span className="text-sm font-bold text-slate-500">
                  / {subscription?.max_motors || '∞'} Max
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Active Commercial Pumps
              </div>
            </div>
            <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-teal-500 rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.round(((subscription?.current_motors || 0) / (subscription?.max_motors || 1)) * 100))}%`,
                }}
              />
            </div>
          </div>

          {/* Card 4: Multi-Site Infrastructure */}
          <div className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800/80 backdrop-blur-sm space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-black uppercase text-slate-400 tracking-wider">
                Registered Sites
              </span>
              <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400">
                <Building2 className="w-4 h-4" />
              </div>
            </div>
            <div>
              <div className="text-2xl font-black text-white">
                {sites.length}{' '}
                <span className="text-sm font-bold text-slate-500">
                  / {subscription?.max_stations || 5} Gateways
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                Multi-tenant Facility Sites
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveTab('ORGANIZATION')}
              className="text-[11px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 transition-colors cursor-pointer"
            >
              <span>View Sites Breakdown</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* ========================================================================= */}
        {/* 3. BUSINESS NAVIGATION TABS */}
        {/* ========================================================================= */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2 overflow-x-auto">
          <button
            type="button"
            onClick={() => setActiveTab('USERS')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-black transition-all cursor-pointer whitespace-nowrap ${
              activeTab === 'USERS'
                ? 'bg-purple-600/20 text-purple-300 border border-purple-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Team &amp; User Accounts ({users.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('SUBSCRIPTION')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-black transition-all cursor-pointer whitespace-nowrap ${
              activeTab === 'SUBSCRIPTION'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <CreditCard className="w-4 h-4" />
            <span>Subscriptions &amp; Quotas</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('ORGANIZATION')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-black transition-all cursor-pointer whitespace-nowrap ${
              activeTab === 'ORGANIZATION'
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <Building2 className="w-4 h-4" />
            <span>Organization &amp; Sites</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('SECURITY')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs font-black transition-all cursor-pointer whitespace-nowrap ${
              activeTab === 'SECURITY'
                ? 'bg-teal-600/20 text-teal-300 border border-teal-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            <span>Role Permissions Matrix</span>
          </button>
        </div>

        {/* ========================================================================= */}
        {/* TAB CONTENT 1: TEAM & USER ACCOUNTS */}
        {/* ========================================================================= */}
        {activeTab === 'USERS' && (
          <div className="space-y-4">
            {/* Search and Filters Bar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 p-4 rounded-3xl bg-slate-900/60 border border-slate-800">
              <div className="relative w-full sm:w-80">
                <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search members by name or email..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500 transition-colors"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <span className="text-xs font-bold text-slate-400">Role:</span>
                <select
                  value={roleFilter}
                  onChange={(e) => setRoleFilter(e.target.value)}
                  className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-bold text-slate-300 focus:outline-none focus:border-purple-500"
                >
                  <option value="ALL">All Roles ({users.length})</option>
                  <option value="STATION_OPERATOR">Station Operator</option>
                  <option value="SITE_MANAGER">Site Manager</option>
                  <option value="ORGANIZATION_ADMIN">Organization Admin</option>
                  <option value="TECHNICIAN">Technician</option>
                  <option value="VIEWER">Read-Only Viewer</option>
                </select>
              </div>
            </div>

            {/* Users Data Table */}
            <div className="rounded-3xl bg-slate-900/60 border border-slate-800 overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800/80 bg-slate-950/40 text-[10px] font-black uppercase text-slate-400 tracking-wider">
                      <th className="py-3.5 px-4 sm:px-6">Member Profile</th>
                      <th className="py-3.5 px-4">Assigned Role</th>
                      <th className="py-3.5 px-4">Account Status</th>
                      <th className="py-3.5 px-4">Tenant Access</th>
                      <th className="py-3.5 px-4 sm:px-6 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40 text-xs">
                    {filteredUsers.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-slate-500">
                          <Users className="w-8 h-8 mx-auto mb-2 opacity-30" />
                          <p className="font-bold">No team members match the search query.</p>
                        </td>
                      </tr>
                    ) : (
                      filteredUsers.map((u) => {
                        const isSelf = u.id === currentUser?.id;
                        const roleObj = AVAILABLE_ROLES.find((r) => r.role === u.role);

                        return (
                          <tr
                            key={u.id}
                            className="hover:bg-slate-800/30 transition-colors group"
                          >
                            {/* Member Profile */}
                            <td className="py-4 px-4 sm:px-6">
                              <div className="flex items-center gap-3">
                                <div className="w-9 h-9 rounded-2xl bg-gradient-to-tr from-purple-600/30 to-indigo-600/30 border border-purple-500/30 flex items-center justify-center font-black text-purple-300 text-xs shrink-0">
                                  {u.name ? u.name.charAt(0).toUpperCase() : 'U'}
                                </div>
                                <div>
                                  <div className="font-black text-white flex items-center gap-1.5">
                                    <span>{u.name}</span>
                                    {isSelf && (
                                      <span className="px-1.5 py-0.2 rounded bg-purple-500/20 text-purple-300 text-[9px] font-bold border border-purple-500/30">
                                        YOU
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-400 flex items-center gap-1">
                                    <Mail className="w-3 h-3 text-slate-500" />
                                    <span>{u.email}</span>
                                  </div>
                                </div>
                              </div>
                            </td>

                            {/* Assigned Role */}
                            <td className="py-4 px-4">
                              <span
                                className={`px-2.5 py-1 rounded-xl text-[10px] font-black border uppercase tracking-wider inline-flex items-center gap-1 ${
                                  roleObj?.badgeColor || 'bg-slate-800 text-slate-400 border-slate-700'
                                }`}
                              >
                                <Shield className="w-3 h-3" />
                                {roleObj?.label || u.role}
                              </span>
                            </td>

                            {/* Status */}
                            <td className="py-4 px-4">
                              <button
                                type="button"
                                onClick={() => !isSelf && handleToggleUserStatus(u)}
                                disabled={isSelf}
                                className={`px-2.5 py-1 rounded-xl text-[10px] font-black inline-flex items-center gap-1 transition-all ${
                                  u.is_active
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/20 cursor-pointer'
                                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/30 hover:bg-rose-500/20 cursor-pointer'
                                } ${isSelf ? 'cursor-default opacity-80' : ''}`}
                              >
                                {u.is_active ? (
                                  <>
                                    <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                    <span>ACTIVE</span>
                                  </>
                                ) : (
                                  <>
                                    <XCircle className="w-3 h-3 text-rose-400" />
                                    <span>DEACTIVATED</span>
                                  </>
                                )}
                              </button>
                            </td>

                            {/* Tenant Info */}
                            <td className="py-4 px-4">
                              <div className="text-[11px] text-slate-400 font-mono">
                                {u.organization_id ? `ORG-${u.organization_id.slice(0, 8)}` : 'Global Enterprise'}
                              </div>
                            </td>

                            {/* Actions */}
                            <td className="py-4 px-4 sm:px-6 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  type="button"
                                  onClick={() => setUserToEditRole(u)}
                                  className="px-2.5 py-1 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-[11px] font-bold border border-slate-700 transition-colors cursor-pointer"
                                >
                                  Edit Role
                                </button>

                                {!isSelf && (
                                  <button
                                    type="button"
                                    onClick={() => setUserToDelete(u)}
                                    title="Delete User"
                                    className="p-1.5 rounded-xl bg-slate-800/80 hover:bg-rose-900/40 text-slate-400 hover:text-rose-400 border border-slate-700 hover:border-rose-500/40 transition-colors cursor-pointer"
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB CONTENT 2: SUBSCRIPTIONS & QUOTA TIERS */}
        {/* ========================================================================= */}
        {activeTab === 'SUBSCRIPTION' && (
          <div className="space-y-6">
            {/* Active Subscription Summary Banner */}
            {subscription && (
              <div className="p-6 rounded-3xl bg-gradient-to-br from-purple-950 via-slate-900 to-slate-950 border border-purple-500/30 shadow-2xl relative overflow-hidden space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="p-3 rounded-2xl bg-gradient-to-tr from-purple-500 to-indigo-600 text-white shadow-lg shadow-purple-500/25">
                      <Sparkles className="w-6 h-6" />
                    </div>
                    <div>
                      <div className="text-[10px] font-black uppercase text-purple-400 tracking-wider">
                        Active Commercial Tier
                      </div>
                      <h3 className="text-xl sm:text-2xl font-black text-white">
                        {subscription.tier} SUBSCRIPTION
                      </h3>
                    </div>
                  </div>

                  <div className="sm:text-right">
                    <span className="px-3 py-1 rounded-xl bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 text-xs font-black">
                      ● Status: {subscription.status}
                    </span>
                    <div className="text-xs text-slate-400 mt-1">
                      Billing Cycle: <span className="text-slate-200 font-bold">{subscription.renewal_date}</span>
                    </div>
                  </div>
                </div>

                {/* Quota Progress Breakdown */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-800">
                  <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-400 font-bold">Motor Quota</span>
                      <span className="text-teal-400 font-black">
                        {subscription.current_motors} / {subscription.max_motors}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-teal-500 rounded-full"
                        style={{
                          width: `${Math.min(100, Math.round((subscription.current_motors / subscription.max_motors) * 100))}%`,
                        }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-500">Commercial pump motor limit</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-400 font-bold">Station Gateways</span>
                      <span className="text-cyan-400 font-black">
                        {subscription.current_stations} / {subscription.max_stations}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-cyan-500 rounded-full"
                        style={{
                          width: `${Math.min(100, Math.round((subscription.current_stations / subscription.max_stations) * 100))}%`,
                        }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-500">Connected physical controllers</p>
                  </div>

                  <div className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-400 font-bold">User Team Seats</span>
                      <span className="text-purple-400 font-black">
                        {subscription.current_users} / {subscription.max_users}
                      </span>
                    </div>
                    <div className="w-full h-2 bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full"
                        style={{
                          width: `${Math.min(100, Math.round((subscription.current_users / subscription.max_users) * 100))}%`,
                        }}
                      />
                    </div>
                    <p className="text-[10px] text-slate-500">Authorized operator seats</p>
                  </div>
                </div>
              </div>
            )}

            {/* Plan Comparison Cards */}
            <div className="space-y-3">
              <h3 className="text-sm font-black uppercase tracking-wider text-slate-400">
                Available Commercial SaaS Plans
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {plans.map((p) => {
                  const isCurrent = subscription?.tier === p.tier;

                  return (
                    <div
                      key={p.tier}
                      className={`p-6 rounded-3xl border flex flex-col justify-between space-y-6 transition-all ${
                        isCurrent
                          ? 'bg-gradient-to-b from-purple-950/40 to-slate-900/90 border-purple-500 shadow-2xl shadow-purple-500/10 ring-2 ring-purple-500/20'
                          : 'bg-slate-900/60 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <div className="space-y-4">
                        <div className="flex items-center justify-between">
                          <span className="text-base font-black text-white">{p.name}</span>
                          {isCurrent && (
                            <span className="px-2.5 py-0.5 rounded-full bg-purple-500 text-white text-[10px] font-black">
                              CURRENT TIER
                            </span>
                          )}
                        </div>

                        <div>
                          <div className="text-3xl font-black text-white font-mono">
                            ${p.price_monthly}/mo
                          </div>
                          <div className="text-xs text-slate-400">Billed monthly with SLA (${p.price_annual}/yr)</div>
                        </div>

                        {/* Quota Highlights */}
                        <div className="space-y-2 py-3 border-y border-slate-800/80 text-xs">
                          <div className="flex items-center justify-between text-slate-300">
                            <span className="text-slate-400">Max Pump Motors:</span>
                            <span className="font-bold text-white font-mono">{p.max_motors}</span>
                          </div>
                          <div className="flex items-center justify-between text-slate-300">
                            <span className="text-slate-400">Max Gateways:</span>
                            <span className="font-bold text-white font-mono">{p.max_stations}</span>
                          </div>
                          <div className="flex items-center justify-between text-slate-300">
                            <span className="text-slate-400">User Seats:</span>
                            <span className="font-bold text-white font-mono">{p.max_users}</span>
                          </div>
                        </div>

                        {/* Features Checklist */}
                        <div className="space-y-2">
                          <div className="text-[10px] font-black uppercase tracking-wider text-slate-500">
                            Included Capabilities
                          </div>
                          {p.features.map((feat, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                              <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                              <span>{feat}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Upgrade / Current Button */}
                      <button
                        type="button"
                        disabled={isCurrent || isUpdatingPlan}
                        onClick={() => setPlanToSwitch(p)}
                        className={`w-full py-3 rounded-2xl text-xs font-black transition-all cursor-pointer ${
                          isCurrent
                            ? 'bg-slate-800 text-purple-300 border border-purple-500/30 cursor-default'
                            : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-lg shadow-purple-600/20'
                        }`}
                      >
                        {isCurrent ? 'Active Plan' : `Upgrade to ${p.name}`}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB CONTENT 3: ORGANIZATION & SITES */}
        {/* ========================================================================= */}
        {activeTab === 'ORGANIZATION' && (
          <div className="space-y-6">
            <div className="p-6 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-4">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-2xl bg-indigo-500/10 text-indigo-400">
                  <Building2 className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-white">Commercial Tenant Profile</h3>
                  <p className="text-xs text-slate-400">Multi-site registration &amp; global organization identity</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-3 border-t border-slate-800 text-xs">
                <div>
                  <span className="text-slate-500 font-bold block">Organization ID</span>
                  <span className="text-white font-mono font-black">{currentUser?.organization_id || 'ORG-ENTERPRISE-01'}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-bold block">Business Contact</span>
                  <span className="text-white font-bold">{currentUser?.email}</span>
                </div>
                <div>
                  <span className="text-slate-500 font-bold block">Timezone</span>
                  <span className="text-white font-bold">{Intl.DateTimeFormat().resolvedOptions().timeZone}</span>
                </div>
              </div>
            </div>

            {/* Sites List */}
            <div className="space-y-3">
              <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">
                Registered Physical Facilities &amp; Sites ({sites.length})
              </h4>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {sites.map((s) => (
                  <div key={s.id} className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-indigo-400" />
                        <span className="text-sm font-black text-white">{s.name}</span>
                      </div>
                      <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-black">
                        OPERATIONAL
                      </span>
                    </div>

                    <div className="text-xs text-slate-400">
                      Location / Region: <span className="text-slate-200 font-bold">{s.location || 'Primary Campus'}</span>
                    </div>

                    <div className="text-[11px] text-slate-500 font-mono">
                      Site UUID: {s.id}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* TAB CONTENT 4: ROLE PERMISSIONS MATRIX */}
        {/* ========================================================================= */}
        {activeTab === 'SECURITY' && (
          <div className="space-y-4">
            <div className="p-6 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-3">
              <h3 className="text-base font-black text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-teal-400" />
                <span>Enterprise RBAC (Role-Based Access Control) Matrix</span>
              </h3>
              <p className="text-xs text-slate-400">
                HydraControl enforces fine-grained operational separation between Business Administrators and Day-to-Day Station Operators.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {AVAILABLE_ROLES.map((r) => (
                <div key={r.role} className="p-5 rounded-3xl bg-slate-900/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className={`px-2.5 py-1 rounded-xl text-xs font-black border ${r.badgeColor}`}>
                      {r.label}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500">{r.role}</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{r.desc}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ========================================================================= */}
      {/* MODAL 1: ADD NEW USER */}
      {/* ========================================================================= */}
      {isAddUserModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 w-full max-w-lg rounded-3xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/30">
                  <UserPlus className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-black text-white">Add Team Member</h3>
                  <p className="text-xs text-slate-400">Provision a new user account with role access</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setIsAddUserModalOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-300">Full Name</label>
                <div className="relative">
                  <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    required
                    placeholder="e.g. John Doe"
                    value={newUserName}
                    onChange={(e) => setNewUserName(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-300">Email Address</label>
                <div className="relative">
                  <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="email"
                    required
                    placeholder="e.g. operator@company.com"
                    value={newUserEmail}
                    onChange={(e) => setNewUserEmail(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-300">Initial Password</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    required
                    placeholder="At least 6 characters"
                    value={newUserPassword}
                    onChange={(e) => setNewUserPassword(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-slate-300">Assigned Operational Role</label>
                <select
                  value={newUserRole}
                  onChange={(e) => setNewRole(e.target.value as UserRole)}
                  className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs font-bold text-white focus:outline-none focus:border-purple-500"
                >
                  {AVAILABLE_ROLES.map((r) => (
                    <option key={r.role} value={r.role}>
                      {r.label} ({r.role})
                    </option>
                  ))}
                </select>
                <p className="text-[10px] text-slate-400 mt-1">
                  {AVAILABLE_ROLES.find((r) => r.role === newUserRole)?.desc}
                </p>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsAddUserModalOpen(false)}
                  className="flex-1 py-2.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-bold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmittingUser}
                  className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-black shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                >
                  {isSubmittingUser && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{isSubmittingUser ? 'Creating...' : 'Create Account'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: EDIT USER ROLE */}
      {/* ========================================================================= */}
      {userToEditRole && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-black text-white">Update Role for {userToEditRole.name}</h3>
              <button
                type="button"
                onClick={() => setUserToEditRole(null)}
                className="text-slate-400 hover:text-white p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-2">
              {AVAILABLE_ROLES.map((r) => (
                <button
                  key={r.role}
                  type="button"
                  onClick={() => handleUpdateRole(userToEditRole, r.role)}
                  className={`w-full p-3 rounded-2xl text-left border flex items-start justify-between transition-all cursor-pointer ${
                    userToEditRole.role === r.role
                      ? 'bg-purple-500/20 border-purple-500 text-purple-200'
                      : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700'
                  }`}
                >
                  <div>
                    <div className="text-xs font-black">{r.label}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">{r.desc}</div>
                  </div>
                  {userToEditRole.role === r.role && <Check className="w-4 h-4 text-purple-400 shrink-0" />}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => setUserToEditRole(null)}
              className="w-full py-2.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-bold transition-colors cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: DELETE USER CONFIRMATION */}
      {/* ========================================================================= */}
      {userToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 w-full max-w-sm rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-rose-400">
              <div className="p-2 rounded-xl bg-rose-500/10 border border-rose-500/30">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-black text-white">Delete User Account?</h3>
                <p className="text-[11px] text-slate-400">This action removes all access.</p>
              </div>
            </div>

            <div className="p-3 bg-slate-950 rounded-2xl border border-slate-800 text-xs space-y-1">
              <div className="font-bold text-white">{userToDelete.name}</div>
              <div className="text-[11px] text-slate-400">{userToDelete.email}</div>
              <div className="text-[10px] font-mono text-purple-400">Role: {userToDelete.role}</div>
            </div>

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() => setUserToDelete(null)}
                className="flex-1 py-2.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-bold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteUser}
                disabled={isDeletingUser}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-black shadow-lg shadow-rose-600/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isDeletingUser && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{isDeletingUser ? 'Deleting...' : 'Confirm Delete'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: PLAN SWITCH CONFIRMATION */}
      {/* ========================================================================= */}
      {planToSwitch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md animate-fade-in">
          <div className="bg-slate-900 border border-slate-800 w-full max-w-md rounded-3xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-purple-400">
              <div className="p-2.5 rounded-xl bg-purple-500/20 border border-purple-500/30">
                <Sparkles className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-black text-white">Switch to {planToSwitch.name}?</h3>
                <p className="text-xs text-slate-400">Upgrade organization commercial quotas</p>
              </div>
            </div>

            <div className="p-4 bg-slate-950 rounded-2xl border border-slate-800 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-400">New Tier Pricing:</span>
                <span className="font-black text-white font-mono">${planToSwitch.price_monthly}/mo</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Motor Quota:</span>
                <span className="font-bold text-teal-300">{planToSwitch.max_motors} Motors</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Gateway Stations:</span>
                <span className="font-bold text-cyan-300">{planToSwitch.max_stations} Stations</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Team User Seats:</span>
                <span className="font-bold text-purple-300">{planToSwitch.max_users} Seats</span>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={() => setPlanToSwitch(null)}
                className="flex-1 py-2.5 rounded-xl border border-slate-800 bg-slate-950 hover:bg-slate-800 text-slate-300 text-xs font-bold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPlanSwitch}
                disabled={isUpdatingPlan}
                className="flex-1 py-2.5 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-black shadow-lg shadow-purple-600/25 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
              >
                {isUpdatingPlan && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>{isUpdatingPlan ? 'Updating Plan...' : 'Confirm Upgrade'}</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
