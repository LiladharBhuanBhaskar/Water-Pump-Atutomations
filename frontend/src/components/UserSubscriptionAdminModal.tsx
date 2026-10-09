import React, { useState, useEffect } from 'react';
import {
  X,
  Users,
  CreditCard,
  UserPlus,
  CheckCircle2,
  Trash2,
  Crown,
  Sparkles,
  Check,
  AlertTriangle,
  Loader2,
  Mail,
  Lock,
  User as UserIcon,
} from 'lucide-react';
import { User, UserRole, UserAdminCreate, SubscriptionPlanInfo, SubscriptionResponse } from '../types';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

interface UserSubscriptionAdminModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const AVAILABLE_ROLES: { role: UserRole; label: string; desc: string }[] = [
  {
    role: 'STATION_OPERATOR',
    label: 'Station Operator',
    desc: 'Full operational access: control motors, adjust tank/sump thresholds, and manage schedules.',
  },
  {
    role: 'SITE_MANAGER',
    label: 'Site Manager',
    desc: 'Supervises physical sites, controllers, safety interlocks, and telemetry diagnostics.',
  },
  {
    role: 'ORGANIZATION_ADMIN',
    label: 'Organization Admin',
    desc: 'Business admin: manage organization users, subscription tier, and system rules.',
  },
  {
    role: 'TECHNICIAN',
    label: 'Field Technician',
    desc: 'Hardware commissioning, sensor calibration, and maintenance logs.',
  },
  {
    role: 'VIEWER',
    label: 'Read-Only Viewer',
    desc: 'Monitor real-time levels and history logs without command execution.',
  },
];

export const UserSubscriptionAdminModal: React.FC<UserSubscriptionAdminModalProps> = ({
  isOpen,
  onClose,
}) => {
  const { user: currentUser } = useAuth();
  const [activeTab, setActiveTab] = useState<'USERS' | 'SUBSCRIPTION'>('USERS');

  // Users State
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState<boolean>(true);
  const [isAddUserOpen, setIsAddUserOpen] = useState<boolean>(false);
  const [newName, setNewName] = useState<string>('');
  const [newEmail, setNewEmail] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [newRole, setNewRole] = useState<UserRole>('STATION_OPERATOR');
  const [submittingUser, setSubmittingUser] = useState<boolean>(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);

  // Subscriptions State
  const [subscription, setSubscription] = useState<SubscriptionResponse | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlanInfo[]>([]);
  const [loadingSub, setLoadingSub] = useState<boolean>(true);
  const [updatingPlan, setUpdatingPlan] = useState<string | null>(null);

  // Feedback State
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadUserData();
      loadSubscriptionData();
    }
  }, [isOpen]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const loadUserData = async () => {
    try {
      setLoadingUsers(true);
      setErrorMessage(null);
      const data = await api.getUsers();
      setUsers(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load user accounts.');
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadSubscriptionData = async () => {
    try {
      setLoadingSub(true);
      const [subData, plansData] = await Promise.all([
        api.getCurrentSubscription(),
        api.getSubscriptionPlans(),
      ]);
      setSubscription(subData);
      setPlans(plansData);
    } catch {
      // fallback
    } finally {
      setLoadingSub(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim() || !newEmail.trim() || !newPassword.trim()) {
      setErrorMessage('All user fields are required.');
      return;
    }
    if (newPassword.length < 8) {
      setErrorMessage('Password must be at least 8 characters.');
      return;
    }

    try {
      setSubmittingUser(true);
      setErrorMessage(null);
      const payload: UserAdminCreate = {
        name: newName.trim(),
        email: newEmail.trim().toLowerCase(),
        password: newPassword,
        role: newRole,
      };
      const created = await api.createUser(payload);
      setUsers((prev) => [...prev, created]);
      setIsAddUserOpen(false);
      setNewName('');
      setNewEmail('');
      setNewPassword('');
      setNewRole('STATION_OPERATOR');
      showToast(`User ${created.name} (${created.role}) created successfully!`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to create user.');
    } finally {
      setSubmittingUser(false);
    }
  };

  const handleToggleUserActive = async (targetUser: User) => {
    try {
      setErrorMessage(null);
      const updated = await api.updateUser(targetUser.id, {
        is_active: !targetUser.is_active,
      });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      showToast(`User ${targetUser.name} ${updated.is_active ? 'activated' : 'deactivated'}.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update user status.');
    }
  };

  const handleDeleteUser = async (targetUser: User) => {
    try {
      setErrorMessage(null);
      await api.deleteUser(targetUser.id);
      setUsers((prev) => prev.filter((u) => u.id !== targetUser.id));
      setUserToDelete(null);
      showToast(`User ${targetUser.name} removed from organization.`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete user.');
    }
  };

  const handleUpgradePlan = async (tier: string) => {
    try {
      setUpdatingPlan(tier);
      setErrorMessage(null);
      const updated = await api.updateSubscriptionPlan({ tier });
      setSubscription(updated);
      showToast(`Subscription upgraded to ${updated.tier} Plan!`);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update subscription.');
    } finally {
      setUpdatingPlan(null);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 bg-slate-950/80 backdrop-blur-md animate-fade-in font-['Plus_Jakarta_Sans',sans-serif]">
      {/* Toast Alert */}
      {toastMessage && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-60 px-4 py-2 rounded-2xl bg-slate-900 text-white text-xs font-bold flex items-center gap-2 shadow-2xl border border-teal-500/50 backdrop-blur-md">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      <div className="bg-white w-full max-w-xl rounded-3xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between bg-gradient-to-r from-slate-900 via-slate-800 to-teal-950 text-white">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-teal-500/20 text-teal-300 border border-teal-500/30">
              <Crown className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-black tracking-tight leading-tight">
                Admin &amp; Business Management
              </h2>
              <p className="text-[11px] text-slate-300">
                Manage organization users, roles &amp; business subscription tiers
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-300 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center border-b border-slate-100 px-5 pt-2 bg-slate-50/50">
          <button
            type="button"
            onClick={() => setActiveTab('USERS')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'USERS'
                ? 'border-teal-600 text-teal-800'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Users &amp; Roles ({users.length})</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab('SUBSCRIPTION')}
            className={`flex items-center gap-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-all cursor-pointer ${
              activeTab === 'SUBSCRIPTION'
                ? 'border-teal-600 text-teal-800'
                : 'border-transparent text-slate-400 hover:text-slate-600'
            }`}
          >
            <CreditCard className="w-4 h-4" />
            <span>Subscription &amp; Quotas</span>
            {subscription && (
              <span className="px-1.5 py-0.2 rounded-md bg-teal-100 text-teal-800 text-[10px] font-black">
                {subscription.tier}
              </span>
            )}
          </button>
        </div>

        {/* Error Banner */}
        {errorMessage && (
          <div className="mx-5 mt-3 p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button
              onClick={() => setErrorMessage(null)}
              className="text-rose-500 hover:text-rose-700 font-bold px-1"
            >
              &times;
            </button>
          </div>
        )}

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* ========================================================================= */}
          {/* TAB 1: USERS & ROLES */}
          {/* ========================================================================= */}
          {activeTab === 'USERS' && (
            <div className="space-y-4">
              {/* Header Action Bar */}
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-black text-slate-900 uppercase tracking-tight">
                    Organization User Accounts
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    Grant operators full pump control, schedule rights, or admin privileges
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsAddUserOpen(true)}
                  className="px-3.5 py-2 rounded-2xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-all"
                >
                  <UserPlus className="w-3.5 h-3.5" />
                  <span>Add New User</span>
                </button>
              </div>

              {/* Add User Modal / Inline Drawer */}
              {isAddUserOpen && (
                <form
                  onSubmit={handleCreateUser}
                  className="p-4 rounded-3xl bg-slate-50 border-2 border-teal-500/30 space-y-3 animate-fade-in"
                >
                  <div className="flex items-center justify-between pb-1 border-b border-slate-200">
                    <span className="text-xs font-black text-slate-800 flex items-center gap-1.5">
                      <UserPlus className="w-4 h-4 text-teal-600" />
                      Create &amp; Assign User
                    </span>
                    <button
                      type="button"
                      onClick={() => setIsAddUserOpen(false)}
                      className="text-slate-400 hover:text-slate-600"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div>
                      <label className="text-[10px] font-bold uppercase text-slate-600">Full Name</label>
                      <div className="relative mt-1">
                        <UserIcon className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="text"
                          required
                          value={newName}
                          onChange={(e) => setNewName(e.target.value)}
                          placeholder="e.g. Rahul Sharma"
                          className="w-full pl-8 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] font-bold uppercase text-slate-600">Email Address</label>
                      <div className="relative mt-1">
                        <Mail className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="email"
                          required
                          value={newEmail}
                          onChange={(e) => setNewEmail(e.target.value)}
                          placeholder="operator@company.com"
                          className="w-full pl-8 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] font-bold uppercase text-slate-600">Password</label>
                      <div className="relative mt-1">
                        <Lock className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
                        <input
                          type="password"
                          required
                          minLength={8}
                          value={newPassword}
                          onChange={(e) => setNewPassword(e.target.value)}
                          placeholder="Min 8 characters"
                          className="w-full pl-8 pr-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-medium focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="text-[10px] font-bold uppercase text-slate-600">Assigned Role</label>
                      <select
                        value={newRole}
                        onChange={(e) => setNewRole(e.target.value as UserRole)}
                        className="w-full mt-1 px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white font-bold text-slate-800 focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                      >
                        {AVAILABLE_ROLES.map((r) => (
                          <option key={r.role} value={r.role}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="text-[10px] text-slate-500 bg-teal-50/60 p-2 rounded-xl border border-teal-100">
                    <span className="font-bold text-teal-800">Role Capability: </span>
                    {AVAILABLE_ROLES.find((r) => r.role === newRole)?.desc}
                  </div>

                  <div className="flex items-center justify-end gap-2 pt-1">
                    <button
                      type="button"
                      onClick={() => setIsAddUserOpen(false)}
                      className="px-3 py-1.5 text-xs font-bold text-slate-600 hover:bg-slate-200/60 rounded-xl"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submittingUser}
                      className="px-4 py-2 rounded-xl bg-teal-600 hover:bg-teal-700 text-white text-xs font-black flex items-center gap-1.5 shadow-md disabled:opacity-50"
                    >
                      {submittingUser && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                      <span>Save &amp; Create User</span>
                    </button>
                  </div>
                </form>
              )}

              {/* Users List */}
              {loadingUsers ? (
                <div className="p-8 text-center text-xs text-slate-400">Loading user accounts...</div>
              ) : users.length === 0 ? (
                <div className="p-8 text-center text-xs text-slate-400 bg-slate-50 rounded-2xl border border-slate-100">
                  No users registered in this organization.
                </div>
              ) : (
                <div className="space-y-2">
                  {users.map((u) => {
                    const isSelf = currentUser?.id === u.id;
                    const roleInfo = AVAILABLE_ROLES.find((r) => r.role === u.role);
                    return (
                      <div
                        key={u.id}
                        className="p-3.5 rounded-2xl border border-slate-200/80 bg-white hover:border-slate-300 flex items-center justify-between gap-3 transition-all"
                      >
                        <div className="flex items-center gap-3 min-w-0 flex-1">
                          <div
                            className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-xs shrink-0 ${
                              u.role === 'SUPER_ADMIN' || u.role === 'ORGANIZATION_ADMIN'
                                ? 'bg-purple-100 text-purple-800'
                                : u.role === 'STATION_OPERATOR' || u.role === 'OWNER'
                                ? 'bg-teal-100 text-teal-800'
                                : 'bg-slate-100 text-slate-700'
                            }`}
                          >
                            {u.name.slice(0, 2).toUpperCase()}
                          </div>

                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-xs font-black text-slate-900 truncate">
                                {u.name}
                              </span>
                              {isSelf && (
                                <span className="px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 text-[9px] font-bold">
                                  YOU
                                </span>
                              )}
                              <span
                                className={`px-2 py-0.5 rounded-lg text-[9px] font-black uppercase ${
                                  u.role.includes('ADMIN')
                                    ? 'bg-purple-50 text-purple-700 border border-purple-200/60'
                                    : u.role === 'STATION_OPERATOR' || u.role === 'OWNER'
                                    ? 'bg-teal-50 text-teal-700 border border-teal-200/60'
                                    : 'bg-slate-100 text-slate-600'
                                }`}
                              >
                                {roleInfo?.label || u.role}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-400 font-medium truncate mt-0.5">
                              {u.email}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          {/* Active / Inactive Toggle */}
                          <button
                            type="button"
                            onClick={() => handleToggleUserActive(u)}
                            disabled={isSelf}
                            title={u.is_active ? 'Deactivate User' : 'Activate User'}
                            className={`px-2.5 py-1 rounded-xl text-[10px] font-bold border transition-colors ${
                              u.is_active
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
                                : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
                            } disabled:opacity-40`}
                          >
                            {u.is_active ? 'Active' : 'Disabled'}
                          </button>

                          {/* Delete User */}
                          {!isSelf && (
                            <button
                              type="button"
                              onClick={() => setUserToDelete(u)}
                              title="Delete User"
                              className="p-1.5 rounded-xl text-slate-400 hover:text-rose-600 hover:bg-rose-50 border border-transparent hover:border-rose-200 transition-colors"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* ========================================================================= */}
          {/* TAB 2: SUBSCRIPTION & PLAN MANAGEMENT */}
          {/* ========================================================================= */}
          {activeTab === 'SUBSCRIPTION' && (
            <div className="space-y-4">
              {loadingSub ? (
                <div className="p-12 text-center flex flex-col items-center justify-center space-y-3">
                  <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
                  <p className="text-xs font-bold text-slate-500">Loading subscription and quota plans...</p>
                </div>
              ) : (
                <>
                  {/* Current Subscription Status Card */}
                  {subscription && (
                <div className="p-4 rounded-3xl bg-gradient-to-br from-teal-900 via-slate-900 to-slate-950 text-white space-y-3 shadow-xl">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="p-1.5 rounded-xl bg-teal-500 text-slate-950">
                        <Sparkles className="w-4 h-4" />
                      </span>
                      <div>
                        <div className="text-[10px] font-black uppercase text-teal-300 tracking-wider">
                          Active Plan Tier
                        </div>
                        <h3 className="text-base font-black tracking-tight">{subscription.tier} TIER</h3>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="px-2.5 py-1 rounded-xl bg-emerald-500/20 border border-emerald-400/40 text-emerald-300 text-[10px] font-black">
                        ● {subscription.status}
                      </span>
                      <div className="text-[10px] text-slate-400 mt-1">
                        Renews: {subscription.renewal_date}
                      </div>
                    </div>
                  </div>

                  {/* Quota Progress Indicators */}
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-800">
                    <div>
                      <div className="text-[10px] text-slate-400 font-bold">Motor Quota</div>
                      <div className="text-sm font-black text-teal-300">
                        {subscription.current_motors} / {subscription.max_motors}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] text-slate-400 font-bold">Station Gateways</div>
                      <div className="text-sm font-black text-cyan-300">
                        {subscription.current_stations} / {subscription.max_stations}
                      </div>
                    </div>

                    <div>
                      <div className="text-[10px] text-slate-400 font-bold">Active Users</div>
                      <div className="text-sm font-black text-emerald-300">
                        {subscription.current_users} / {subscription.max_users}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Plans Comparison Grid */}
              <div className="space-y-2">
                <h4 className="text-xs font-black uppercase tracking-wider text-slate-600">
                  Select Business Subscription Plan
                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  {plans.map((p) => {
                    const isCurrent = subscription?.tier === p.tier;
                    const isProcessing = updatingPlan === p.tier;

                    return (
                      <div
                        key={p.tier}
                        className={`p-3.5 rounded-3xl border flex flex-col justify-between space-y-3 transition-all ${
                          isCurrent
                            ? 'bg-gradient-to-b from-teal-50/50 to-white border-teal-500 shadow-md ring-2 ring-teal-500/20'
                            : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                      >
                        <div className="space-y-1.5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-black text-slate-900">{p.name}</span>
                            {isCurrent && (
                              <span className="px-1.5 py-0.2 rounded-md bg-teal-600 text-white text-[9px] font-black">
                                CURRENT
                              </span>
                            )}
                          </div>

                          <div className="text-base font-black text-slate-900">
                            ${p.price_monthly}
                            <span className="text-[10px] text-slate-400 font-medium">/mo</span>
                          </div>

                          <ul className="space-y-1 pt-1 border-t border-slate-100 text-[10px] text-slate-600 font-medium">
                            {p.features.map((feat, idx) => (
                              <li key={idx} className="flex items-start gap-1">
                                <Check className="w-3 h-3 text-teal-600 shrink-0 mt-0.5" />
                                <span>{feat}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleUpgradePlan(p.tier)}
                          disabled={isCurrent || !!updatingPlan}
                          className={`w-full py-2 rounded-xl text-xs font-black transition-all ${
                            isCurrent
                              ? 'bg-teal-100 text-teal-800 cursor-default'
                              : 'bg-slate-900 hover:bg-teal-600 text-white shadow-xs cursor-pointer'
                          } disabled:opacity-50`}
                        >
                          {isProcessing ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin mx-auto" />
                          ) : isCurrent ? (
                            'Active Tier'
                          ) : (
                            'Switch to Plan'
                          )}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
              </>
              )}
            </div>
          )}
        </div>

        {/* Delete Confirmation Dialog */}
        {userToDelete && (
          <div className="p-4 bg-rose-50 border-t border-rose-200 flex items-center justify-between gap-3 animate-fade-in">
            <div className="text-xs text-rose-900">
              <span className="font-bold">Confirm User Deletion: </span>
              Remove {userToDelete.name} ({userToDelete.email})?
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setUserToDelete(null)}
                className="px-3 py-1.5 rounded-xl bg-white border border-rose-200 text-xs font-bold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleDeleteUser(userToDelete)}
                className="px-3 py-1.5 rounded-xl bg-rose-600 text-white text-xs font-black shadow-sm"
              >
                Delete
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
