import { apiRequest, setApiAuthSession } from './api';
import { PortalJwtSession, PortalUser } from './types';

type PortalAuthApi = {
  requireJwtUser: () => Promise<PortalUser>;
  requireJwtSession: () => Promise<PortalJwtSession>;
  getJwtSession?: () => Promise<{ authenticated?: boolean; error?: string } & Partial<PortalJwtSession>>;
  clearJwtSession?: () => void;
};

declare global {
  interface Window {
    portalAuth?: PortalAuthApi;
  }
}

export function getUserDisplayName(user: PortalUser | null | undefined): string {
  const name = String(user?.name || '').trim();
  return name || '已登录用户';
}

export function formatJobFunctions(jobFunctions: PortalUser['job_functions']): string {
  if (!Array.isArray(jobFunctions) || jobFunctions.length === 0) {
    return '';
  }

  const labels: Record<string, string> = {
    qa: '测试',
    program: '程序',
    art: '美术',
    ta: 'TA',
    producer: '制作人',
    planner: '策划',
    pm: 'PM',
    ops_am: '运营-AM',
    ops_cs: '运营-客服',
    ops_marketing: '运营-美宣',
    platform_backend: '中台-后端',
    platform_sdk: '中台-SDK',
    platform_frontend: '中台-前端',
    platform_pm: '中台-PM',
    soulknight: '元气骑士项目',
  };

  return jobFunctions.map((code) => labels[code] || code).join(' / ');
}

export function getJobTitleText(user: PortalUser | null | undefined): string {
  if (user?.job_title) {
    return user.job_title;
  }

  const jobFunctionsText = formatJobFunctions(user?.job_functions);
  if (jobFunctionsText) {
    return jobFunctionsText;
  }

  if (user?.job_title_status === 'empty') {
    return '职位信息暂未配置';
  }

  if (user?.job_title_status === 'not_found') {
    return '未匹配到用户目录';
  }

  if (user?.job_title_status === 'error') {
    return '职位信息获取失败';
  }

  return '职位信息暂未获取';
}

export function isSoulknightProjectUser(user: PortalUser | null | undefined): boolean {
  return Array.isArray(user?.job_functions) && user.job_functions.includes('soulknight');
}

export function isTestUser(user: PortalUser | null | undefined): boolean {
  const jobFunctions = Array.isArray(user?.job_functions) ? user.job_functions : [];
  const title = String(user?.job_title || '').toLowerCase();
  return (
    jobFunctions.includes('qa') ||
    title.includes('测试') ||
    title.includes('qa') ||
    title.includes('quality') ||
    title.includes('test')
  );
}

export async function requirePortalSession(): Promise<PortalJwtSession> {
  if (!window.portalAuth?.requireJwtUser || !window.portalAuth.requireJwtSession) {
    throw new Error('门户登录脚本加载失败，请刷新页面或检查网络');
  }

  try {
    const user = await window.portalAuth.requireJwtUser();
    const session = await window.portalAuth.requireJwtSession();
    const resolvedSession = { ...session, user: session.user || user };
    setApiAuthSession({
      token: resolvedSession.token,
      audience: resolvedSession.audience || window.location.origin,
    });
    return resolvedSession;
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err || '');
    if (message.includes('SSO_JWT_INVALID')) {
      window.portalAuth?.clearJwtSession?.();
      void window.portalAuth?.requireJwtUser?.();
      throw new Error('登录凭证已失效，正在重新登录/请重新登录');
    }
    throw err;
  }
}

export async function migrateCurrentUserBorrowerData() {
  await apiRequest<{ migrated?: number }>('/api/current-user/migrate-borrower-data', {
    method: 'POST',
  });
}
